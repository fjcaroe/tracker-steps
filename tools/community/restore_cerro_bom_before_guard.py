"""Adopt the original Cerro BoM field during a new logical restore, before its first row guard is created."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess

from check_cerro_studio_strict import RUNTIME, addon_roots, run, tree_sha
from restore_cerro_studio_strict import GIB, ROOT, SPACE, TARGET as SOURCE, copy_filestore, module_census, pg, references, sql

TARGET = 'COMMUNITY_CERRO_BOM_ADOPTED_20261126U42B'
DEST = Path('/opt/steps-validation/community-cerro-bom-adopted-20261126U42B')
COLD_TARGET = 'COMMUNITY_CERRO_BOM_COLD_20261126U42H'
COLD_DEST = Path('/opt/steps-validation/community-cerro-studio-cold-20261126U42H')
PROFILE = ROOT / 'bom-restore-2d6b0a1c73e6'
PROVIDER = PROFILE / 'step_cerro_bom_company'
GUARD = 'step_anchor_preserve_original_row'
FIELD = 30516
OWN_ALIAS = 'field_mrp_bom__x_studio_compaia'


def fingerprint(db):
    fields = sql(db, """SELECT count(*),md5(string_agg((CASE WHEN id=30516 THEN to_jsonb(f)-'state'
           ELSE to_jsonb(f) END)::text,chr(10) ORDER BY id)) FROM ir_model_fields f""")
    ids = sql(db, """SELECT count(*),md5(string_agg(to_jsonb(d)::text,chr(10) ORDER BY id)) FROM ir_model_data d
        WHERE (module,name)<>('step_cerro_bom_company','field_mrp_bom__x_studio_compaia')""")
    bom = sql(db, 'SELECT count(*),md5(string_agg(to_jsonb(b)::text,chr(10) ORDER BY id)) FROM mrp_bom b')
    return {'fields_except_adopted_state': fields, 'xml_ids_except_new_alias': ids, 'boms': bom}


def guard(db):
    return sql(db, """SELECT pg_get_triggerdef(t.oid) FROM pg_trigger t
        WHERE t.tgrelid='ir_model_fields'::regclass AND t.tgname='step_anchor_preserve_original_row'
        AND NOT t.tgisinternal AND t.tgenabled='O'""")


def all_guards(db):
    return sql(db, """SELECT count(*),md5(string_agg(pg_get_triggerdef(t.oid)||t.tgenabled::text||
            md5(pg_get_functiondef(t.tgfoid)),chr(10) ORDER BY t.tgrelid::regclass::text,t.tgname))
            FROM pg_trigger t WHERE NOT t.tgisinternal AND t.tgname LIKE 'step_anchor_%'""")


def before_guard(source=SOURCE, target=TARGET, dest=DEST):
    from restore_cerro_studio_strict import SOURCE as library, FILES
    if (source,target,dest) not in ((SOURCE,TARGET,DEST),(library,COLD_TARGET,COLD_DEST)):
        raise ValueError('Unknown private Cerro source and destination')
    originals = FILES if source == library else ROOT / 'data/filestore' / source
    if tree_sha(PROVIDER) != 'e27bebe09c163549cf975cdbe2f8d6e301b6f51a9bdeaa19997eeac3b101db7f':
        raise ValueError('The BoM provider differs from its admission package')
    dest.mkdir(mode=0o751, parents=True, exist_ok=True)
    postgres = pwd.getpwnam('postgres')
    source_state = module_census(source)
    assert not any(source_state[k] for k in ('pending', 'enterprise', 'non_free'))
    assert sql(source, "SELECT state FROM ir_model_fields WHERE id=30516 AND model='mrp.bom' AND name='x_studio_compaia'") == 'manual'
    pg_dir = Path(sql('postgres', 'SHOW data_directory'))
    space = Path(sql('postgres', "SELECT pg_tablespace_location(oid) FROM pg_tablespace WHERE spcname='" + SPACE + "'"))
    size = int(sql('postgres', "SELECT pg_database_size('" + source + "')"))
    memory = int(next(l.split()[1] for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:'))) * 1024
    if (not space.resolve().is_relative_to('/opt/steps-validation') or shutil.disk_usage(pg_dir).free < 5*GIB
            or shutil.disk_usage(space).free < max(8*GIB, size*4) or memory < 1536*1024**2):
        raise ValueError('Tablespace, PostgreSQL or memory reservation is insufficient')
    backup = dest / 'source.dump'
    seal = dest / 'source-seal.json'
    if not seal.exists():
        if backup.exists():
            raise ValueError('An earlier archive needs verification before reuse')
        with backup.open('xb') as out:
            subprocess.run(['runuser', '-u', 'postgres', '--', 'pg_dump', '-Fc', '--no-tablespaces', '-d', source], stdout=out, check=True)
        os.chown(backup, -1, postgres.pw_gid)
        backup.chmod(0o640)
        evidence = {'source': source, 'target': target, 'sha256': hashlib.sha256(backup.read_bytes()).hexdigest(),
                    'rows': fingerprint(source), 'guards': all_guards(source), 'field_guard': guard(source), 'census': source_state}
        seal.write_text(json.dumps(evidence, sort_keys=True))
    evidence = json.loads(seal.read_text())
    assert evidence['source'] == source and evidence['target'] == target
    assert hashlib.sha256(backup.read_bytes()).hexdigest() == evidence['sha256']
    assert evidence['field_guard'].startswith('CREATE TRIGGER ' + GUARD + ' ')
    toc = subprocess.check_output(['pg_restore', '-l', str(backup)], text=True).splitlines()
    deferred = [line for line in toc if ' TRIGGER public ir_model_fields ' + GUARD + ' ' in line]
    if len(deferred) != 1:
        raise ValueError('The original row trigger is not unambiguous in the archive')
    restricted = dest / 'first-restore.list'
    restricted.write_text('\n'.join(line for line in toc if line not in deferred) + '\n')
    os.chown(restricted, -1, postgres.pw_gid)
    restricted.chmod(0o640)
    owner = sql('postgres', f"SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='{target}'")
    if not owner:
        locale = sql('postgres', f"SELECT pg_encoding_to_char(encoding),datcollate,datctype FROM pg_database WHERE datname='{source}'").split('|')
        pg('createdb', '--owner=dev_odoo18', '--template=template0', '--tablespace=' + SPACE,
           '--encoding=' + locale[0], '--lc-collate=' + locale[1], '--lc-ctype=' + locale[2], target)
    elif owner != 'dev_odoo18':
        raise ValueError('Another owner already uses the proposed database')
    if not sql(target, "SELECT coalesce(to_regclass('public.ir_model_fields')::text,'')"):
        pg('pg_restore', '--exit-on-error', '--single-transaction', '--no-tablespaces',
           '-L', str(restricted), '-d', target, str(backup))
    assert module_census(target) == evidence['census']
    assert fingerprint(target) == evidence['rows']
    if not guard(target):
        if sql(target, 'SELECT state FROM ir_model_fields WHERE id=30516') != 'manual':
            raise ValueError('The original unadopted field is missing')
        # Use the same migration as the actual addon and create the exact archived
        # trigger in the same transaction, before permitting any Odoo registry.
        exe = """import importlib.util,sys,psycopg2
from types import SimpleNamespace
sys.path.insert(0,sys.argv[1])
p=importlib.util.spec_from_file_location('cerro_verified_bom_hook',sys.argv[2]);m=importlib.util.module_from_spec(p);p.loader.exec_module(m)
with psycopg2.connect(dbname=sys.argv[3],host='/var/run/postgresql') as conn, conn.cursor() as cr:
    cr.execute("SELECT current_database(),current_user");assert cr.fetchone()==(sys.argv[3],'postgres')
    m.adopt_company_field(SimpleNamespace(cr=cr))
    cr.execute("INSERT INTO ir_model_data(module,name,model,res_id,noupdate,create_uid,write_uid,create_date,write_date) VALUES ('step_cerro_bom_company','field_mrp_bom__x_studio_compaia','ir.model.fields',30516,true,1,1,now(),now())")
    cr.execute(sys.stdin.read())
"""
        subprocess.run(['runuser', '-u', 'postgres', '--', '/usr/bin/python3.10', '-c', exe,
                        str(RUNTIME), str(PROVIDER / 'hooks.py'), target], input=evidence['field_guard'], text=True, check=True)
    assert guard(target) == evidence['field_guard'] and all_guards(target) == evidence['guards']
    assert sql(target, 'SELECT state FROM ir_model_fields WHERE id=30516') == 'base'
    assert fingerprint(target) == evidence['rows']
    check = """import psycopg2,sys
with psycopg2.connect(dbname=sys.argv[1]) as conn, conn.cursor() as cr:
    try:
        cr.execute("UPDATE ir_model_fields SET state='manual' WHERE id=30516")
    except psycopg2.errors.CheckViolation as error:
        assert 'Original anchor guard' in str(error); conn.rollback()
    else:
        conn.rollback();raise ValueError('The restored guard did not refuse the write')
"""
    subprocess.run(['runuser', '-u', 'postgres', '--', '/usr/bin/python3.10', '-c', check, target], check=True)
    files = references(target)
    copy_filestore(originals, dest, target, files)
    receipt = {'target': target, 'sole_original_metadata_change': [FIELD, 'manual', 'base'], 'guards': evidence['guards'],
               'guard_rejected_reverse': True, 'rows': evidence['rows'], 'archive_sha256': evidence['sha256'], 'objects': len(files)}
    (dest / 'adopted-receipt.json').write_text(json.dumps(receipt, sort_keys=True))
    return receipt


def main():
    with open('/run/lock/steps-environments.lock', 'rb') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        if not (DEST / 'adopted-receipt.json').exists():
            before_guard()
        existing = json.loads((DEST / 'adopted-receipt.json').read_text())
        assert existing['target'] == TARGET and guard(TARGET) == guard(SOURCE)
        roots = [PROFILE, *addon_roots(TARGET)]
        opts = dict(database=TARGET, directory=DEST, roots=roots)
        # The strict source retains the original Studio field and the tested products views.
        if not (DEST / 'baseline.json').is_file():
            capture = "import json,sys\nsys.path.insert(0," + repr(str(ROOT/'tools')) + ")\n"
            capture += "from probe_cerro_bom_catalogue import reference,rendered\nactor=env['res.users'].browse(6)\n"
            capture += "print('BOM_BASELINE',json.dumps(dict(reference=reference(env),visible=rendered(env,actor),operator=actor.id),sort_keys=True))\nenv.cr.rollback()"
            run('bom-source', [], capture, database=SOURCE, directory=ROOT)
            text = (ROOT / 'bom-source.log').read_text()
            line, = [l.split(' ',1)[1] for l in text.splitlines() if l.startswith('BOM_BASELINE ')]
            (DEST / 'baseline.json').write_text(line)
        if sql(TARGET, "SELECT state FROM ir_module_module WHERE name='step_cerro_bom_company'") != 'installed':
            run('install-bom', ['-i', 'step_cerro_bom_company'], **opts)
        assert sql(TARGET, "SELECT latest_version FROM ir_module_module WHERE name='step_cerro_bom_company' AND state='installed'") == '18.0.1.0.1'
        baseline = json.loads((DEST / 'baseline.json').read_text())
        probe = 'import json,sys\nsys.path.insert(0,' + repr(str(ROOT/'tools')) + ')\nfrom probe_cerro_bom_catalogue import exercise\n'
        probe += "print('STRICT_BOM',json.dumps(exercise(env," + repr(baseline) + "),sort_keys=True))"
        run('bom-user', [], probe, **opts)
        text = (DEST / 'bom-user.log').read_text()
        result, = [json.loads(l.split(' ',1)[1]) for l in text.splitlines() if l.startswith('STRICT_BOM ')]
        census = module_census(TARGET)
        assert not any(census[k] for k in ('pending', 'enterprise', 'non_free'))
        result['census'] = census
        (DEST / 'qualified-bom.json').write_text(json.dumps(result,sort_keys=True))
        print(json.dumps(result,sort_keys=True))


if __name__ == '__main__':
    main()
