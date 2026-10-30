"""Guarded private-only handover trial on a fresh, original-identity Cerro copy.

This deliberately quarantines out-of-scope installed products in the NEW copy;
their tables/data/metadata are retained. It is not an integral conversion or a
production deploy. No uninstall API, license/expiry update or master import.
"""
import argparse
import ast
import configparser
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys

import payroll_configuration_adoption_preflight as gate
import validate_agriculture_core as preservation
from validate_community_reports import sql
from offline_process import offline_odoo
from build_original_anchor_profile import OWN
from build_original_anchor_guards import guard_specs, render_sql


CAPSULE = Path('/opt/steps-validation/community-original-config-20261029/configuration-capsule-C.json')
CAPSULE_SHA = '14b18ced97032ec27c306ed4c71c46f0c3d56e324d0eace4f0c8f2c86544e140'
RUNTIME = Path('/opt/steps-validation/community-foundation-final-20261027/community-runtime')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(value, stream, indent=2)


def manifest(folder):
    return ast.literal_eval((folder / '__manifest__.py').read_text(encoding='utf-8-sig'))


def safe_closure(roots, requested):
    selected, visiting = set(), set()
    def visit(name):
        assert re.fullmatch(r'[a-z_][a-z0-9_]*', name)
        if name in selected:return
        assert name not in visiting, 'Dependency cycle'
        candidates = [root / name for root in roots if (root / name / '__manifest__.py').is_file()]
        assert len(candidates) == 1, 'Missing/shadowed free module: ' + name
        spec = manifest(candidates[0]);assert spec.get('license', 'LGPL-3') in ('LGPL-3', 'AGPL-3')
        assert name not in ('hr_payroll', 'hr_payroll_account', 'step_expire_database')
        visiting.add(name)
        for item in spec.get('depends', []):visit(item)
        visiting.remove(name);selected.add(name)
    for item in requested:visit(item)
    return selected


def original_columns(database, tables):
    rows = json.loads(sql(database, "SELECT jsonb_agg(jsonb_build_array(table_name,column_name) "
        "ORDER BY table_name,ordinal_position) FROM information_schema.columns WHERE table_schema='public' "
        'AND table_name IN (' + ','.join(gate.literal(t) for t in tables) + ')'))
    result = {table: [] for table in tables}
    for table, column in rows:result[table].append(column)
    return result


def column_snapshot(database, columns):
    queries = []
    for table, names in columns.items():
        assert names and re.fullmatch('[a-z_][a-z0-9_]*', table)
        keys = 'ARRAY[' + ','.join(gate.literal(n) for n in names) + ']::text[]'
        queries.append("SELECT " + gate.literal(table) + " AS name,json_build_object('rows',count(*),"
            "'hash',md5(coalesce(string_agg(j::text,E'\\n' ORDER BY j::text),''))) AS value FROM "
            '(SELECT (SELECT jsonb_object_agg(k,to_jsonb(t)->k) FROM unnest(' + keys + ') k) j FROM public.'
            + gate.identifier(table) + ' t) data')
    return json.loads(sql(database, 'SET jit=off; SELECT json_object_agg(name,value) FROM ('
        + ' UNION ALL '.join(queries) + ') snapshot'))


def prepare_roles(database):
    roles = {}
    for suffix in ('user', 'manager'):
        name = 'group_hr_payroll_' + suffix
        rows = json.loads(sql(database, "SELECT json_agg(t) FROM (SELECT d.id,d.model,d.res_id,d.noupdate "
            "FROM ir_model_data d JOIN res_groups g ON g.id=d.res_id WHERE d.module='hr_payroll' AND d.name="
            + gate.literal(name) + " AND d.model='res.groups') t"))
        assert rows and len(rows) == 1
        target = 'group_payroll_' + suffix; ident = rows[0]['res_id']
        existing = json.loads(sql(database, "SELECT coalesce(json_agg(t),'[]'::json) FROM "
            "(SELECT model,res_id,noupdate FROM ir_model_data WHERE module='payroll' AND name=" + gate.literal(target) + ') t'))
        assert not existing or existing == [{'model':'res.groups','res_id':ident,'noupdate':True}]
        if not existing:
            sql(database, "INSERT INTO ir_model_data(module,name,model,res_id,noupdate) VALUES "
                "('payroll'," + gate.literal(target) + ",'res.groups'," + str(ident) + ',true)')
        roles[target] = ident
    return roles


def prepare_nullable_company_columns(database):
    """New provider columns do not invent an owner for global native masters."""
    result = []
    for table, column in (('hr_payroll_structure', 'company_id'), ('hr_payroll_structure', 'parent_id'),
            ('hr_salary_rule', 'company_id'), ('hr_salary_rule_category', 'company_id')):
        exists = sql(database, "SELECT data_type FROM information_schema.columns WHERE table_schema='public' "
            'AND table_name=' + gate.literal(table) + ' AND column_name=' + gate.literal(column))
        if not exists:
            sql(database, 'ALTER TABLE ' + gate.identifier(table) + ' ADD COLUMN ' + gate.identifier(column) + ' integer')
            assert sql(database, 'SELECT count(*) FROM ' + gate.identifier(table) + ' WHERE ' + gate.identifier(column) + ' IS NOT NULL') == '0'
        else:
            assert exists == 'integer', 'Existing company storage needs its own reviewed bridge'
        result.append({'table': table, 'column': column, 'added_nullable': not bool(exists),
            'original_owner_or_parent_inferred': False})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True);parser.add_argument('--database',required=True)
    args = parser.parse_args();root=args.root.resolve();database=args.database
    assert os.geteuid() == 0 and re.fullmatch(r'MANAGEMENT_QA_CERRO_PAYROLL_API_ORIGINAL_HANDOVER_[A-Za-z0-9_]+',database)
    assert root.parent == Path('/opt/steps-validation') and root.name.startswith('community-original-handover-')
    assert (root/'anchor-profile.json').is_file() and sha(CAPSULE) == CAPSULE_SHA
    source=root/'source';stage=root/'anchor';assert not stage.exists();stage.mkdir(mode=0o750)
    reference = database.replace('_HANDOVER_', '_REFERENCE_')
    assert reference != database and len(reference) <= 63 and len(database) <= 63
    capsule=json.loads(CAPSULE.read_text());gate.capsule_rows(capsule)
    dev=configparser.ConfigParser(interpolation=None);assert dev.read('/etc/dev_odoo18.conf')
    assert dev['options']['db_name']=='LAB_TAREAS';dbuser=dev['options']['db_user']
    prod=configparser.ConfigParser(interpolation=None);assert prod.read('/etc/odoo18-cerroelplomo.conf')
    assert prod['options']['db_name']=='CERRO_EL_PLOMO'
    roots=[root/'runtime-addons',root/'engine-addons',RUNTIME/'addons',RUNTIME/'odoo/addons']
    required=safe_closure(roots,OWN)
    owner=pwd.getpwnam('odoo');data=stage/'data';data.mkdir()
    with open('/run/lock/steps-environments.lock','a') as lease:
        print('ORIGINAL_ANCHOR_WAITING_FOR_SHARED_LEASE',flush=True);fcntl.flock(lease,fcntl.LOCK_EX)
        assert not sql('postgres','SELECT 1 FROM pg_database WHERE datname='+gate.literal(database))
        assert not sql('postgres','SELECT 1 FROM pg_database WHERE datname='+gate.literal(reference))
        for path,reserve in ((Path(sql('postgres','SHOW data_directory')),5*1024**3),(root,2*1024**3)):
            st=os.statvfs(path);assert st.f_bavail*st.f_frsize>=reserve
        assert sql('postgres',"SELECT pg_tablespace_location(oid) FROM pg_tablespace WHERE spcname='steps_community_storage_20261028_community'")=='/opt/steps-validation/community-payroll-storage-20261028/community'
        assert sql('CERRO_EL_PLOMO','SELECT count(*) FROM hr_payslip')=='0', 'This trial admits Cerro with no payroll history only'
        assert sql('CERRO_EL_PLOMO',"SELECT count(*) FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove')")=='0'
        subprocess.run(['sudo','-u','postgres','createdb','--owner='+dbuser,'--tablespace=steps_community_storage_20261028_community',database],check=True)
        with (stage/'source.dump').open('wb') as out:
            subprocess.run(['sudo','-u','postgres','pg_dump','-Fc','CERRO_EL_PLOMO'],stdout=out,check=True)
        with (stage/'source.dump').open('rb') as inp,(stage/'restore.log').open('w') as log:
            subprocess.run(['sudo','-u','postgres','pg_restore','--exit-on-error','--no-owner','--no-acl','--no-comments',
                '--no-tablespaces','--role='+dbuser,'-d',database],stdin=inp,stderr=log,check=True)
        if (root/'oca-original-anchor-history-deletion.json').exists():
            from preflight_original_history_storage import capture as capture_history_storage
            from audit_multifront_installation import readonly_sql as history_readonly_sql
            # The actual fresh restore is observed BEFORE the first Odoo
            # process, required fields, defaults or source module state changes.
            write(stage/'before-initialization-storage.json',capture_history_storage(history_readonly_sql,database,'anchored'))
        sql(database,'UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false;')
        # An untouched native metadata control from exactly the same dump. Raw
        # readonly helper plans are constructed from this real database later.
        subprocess.run(['sudo','-u','postgres','createdb','--owner='+dbuser,
            '--tablespace=steps_community_storage_20261028_community','--template='+database,reference],check=True)
        store=data/'filestore'/database;store.mkdir(parents=True)
        subprocess.run(['rsync','-a',str(Path(prod['options']['data_dir'])/'filestore/CERRO_EL_PLOMO')+'/',str(store)+'/'],check=True)
        preservation.MODULES=('step_cosecha','step_labor_operations_core')
        identity=preservation.identity_contract(database);write(stage/'identity-before.json',identity)
        before=preservation.snapshot(database)
        counters={name:value for name,value in before.items() if re.fullmatch(r'ir_sequence_[0-9]+(_[0-9]+)?',name)}
        write(stage/'counters-before.json',counters)
        columns=original_columns(database,sorted(set(before)-set(counters)));write(stage/'original-columns.json',columns)
        write(stage/'business-before.json',column_snapshot(database,columns))
        facts=gate.run_snapshot(database,gate.queries(capsule,source=True))
        assert all(facts['source_hash:'+table][0]['rows_sha256']==values['rows_sha256']
            for table,values in capsule['tables'].items()), 'Fresh source differs from the sealed original capsule'
        external=gate.run_snapshot(database,gate.external_queries(capsule,facts))
        preflight={'source_metadata':facts,'source_external_metadata':external}
        report_rows=json.loads(sql(database,"SELECT json_agg(to_jsonb(t)::text) FROM ir_act_report_xml t WHERE id=462"))
        report_columns=[row['column_name'] for row in facts['columns'] if row['table_name']=='ir_act_report_xml']
        identity['original_report_462']={'table':'ir_act_report_xml','columns':report_columns,'rows_json':report_rows}
        # Replace only this newly captured private artifact before its seal is used.
        (stage/'identity-before.json').write_text(json.dumps(identity,indent=2));(stage/'identity-before.json').chmod(0o600)
        write(stage/'source-preflight.json',preflight)
        specs=guard_specs(capsule,identity,identity,preflight);guard_sql=render_sql(database,specs)
        (stage/'guards.sql').write_text(guard_sql);(stage/'guards.sql').chmod(0o600);sql(database,guard_sql)
        tests=[]
        for statement in ("DELETE FROM hr_salary_rule WHERE id=1", "UPDATE ir_model_data SET noupdate=NOT noupdate WHERE id=58550", "TRUNCATE hr_salary_rule CASCADE"):
            r=subprocess.run(['sudo','-u','postgres','psql','-Xq','-v','ON_ERROR_STOP=1','-d',database],input='BEGIN; '+statement+'; ROLLBACK;',text=True,capture_output=True)
            assert r.returncode!=0 and 'Original anchor guard:' in r.stderr
            tests.append({'denied':True,'statement_sha256':hashlib.sha256(statement.encode()).hexdigest()})
        write(stage/'guard-runtime-negative-tests.json',tests)
        write(stage/'new-company-columns.json',prepare_nullable_company_columns(database))
        installed=json.loads(sql(database,"SELECT json_agg(t) FROM (SELECT name,state,license,latest_version FROM ir_module_module WHERE state='installed' ORDER BY name) t"))
        keep=set(required)
        for row in installed:
            if row['license']=='OEEL-1' or row['name'].startswith('step'):continue
            try:keep.update(safe_closure(roots,(row['name'],)))
            except AssertionError:pass
        quarantined=[row for row in installed if row['name'] not in keep]
        sql(database,"UPDATE ir_module_module SET state='uninstalled' WHERE state='installed' AND name NOT IN ("+','.join(gate.literal(x) for x in sorted(keep))+')')
        roles=prepare_roles(database)
        (stage/'capsule.json').write_bytes(CAPSULE.read_bytes());(stage/'capsule.json').chmod(0o600)
        write(stage/'handover-plan.json',{'profile':'original-cohort-anchor','database':database,'reference_database':reference,'required':sorted(required),
            'preserved_free_installed':sorted(keep),'quarantined_modules':quarantined,'role_aliases':roles,
            'source_dump_sha256':sha(stage/'source.dump'),'all_products_operational':False,
            'deadline_resolved':False,'production_changed':False,'paid_history_admitted':False})
        for path in (stage,*stage.rglob('*')):
            if not path.is_symlink():os.chown(path,owner.pw_uid,owner.pw_gid)
        opts=['-c','/etc/dev_odoo18.conf','-d',database,'--db-filter=^'+database+'$', '--db_host=/var/run/postgresql',
            '--addons-path='+','.join(map(str,roots[:3])),'--data-dir='+str(data),'--load=base,web','--workers=0',
            '--max-cron-threads=0','--without-demo=all','--no-http','--stop-after-init']
        normal=['sudo','-u','odoo','/usr/bin/python3.10',str(RUNTIME/'odoo-bin'),'shell']
        # Use the standard UI installer state transition, rather than CLI -i.
        # Graph.init propagates to already installed consumers and would force
        # reload of their noupdate business masters. New modules in 'to install'
        # still receive the official init mode; existing consumers update.
        prepare=('import json; names='+repr(list(OWN))+'; '
            'env["ir.module.module"].update_list(); '
            'new=env["ir.module.module"].search([("name","in",names)]); '
            'assert len(new)==len(names) and all(m.state=="uninstalled" for m in new); '
            'new.button_install(); '
            'assert all(m.state=="to install" for m in new); '
            'provider=env["ir.module.module"].search([("name","=","l10n_cl_simpledigital_payroll")]); '
            'assert len(provider)==1 and provider.state=="installed"; '
            'receipt={"official_button_install":True,"cli_init_used":False,"new_roots":names,'
            '"native_provider_reinstalled":False,"original_provider_state":provider.state}; '
            'env.cr.commit(); open('+repr(str(stage/'official-install-plan.json'))
            +',"x").write(json.dumps(receipt,indent=2))')
        with (stage/'prepare-bootstrap.log').open('x') as log:
            prepared=subprocess.run(offline_odoo(normal+opts+['--logfile='+str(stage/'prepare.log')]),
                input=prepare,text=True,stdout=log,stderr=subprocess.STDOUT)
        assert prepared.returncode==0 and (stage/'official-install-plan.json').is_file(), 'Official module state preparation failed'
        (stage/'official-install-plan.json').chmod(0o600)
        opts+=['-u',','.join(OWN)]
        command=['sudo','-u','odoo','/usr/bin/python3.10',str(source/'tools/community/run_original_anchor_loader.py'),
            '--runtime',str(RUNTIME),'--database',database,'--capsule',str(stage/'capsule.json'),'--capsule-sha256',CAPSULE_SHA,
            '--identity-before',str(stage/'identity-before.json'),'--identity-before-sha256',sha(stage/'identity-before.json'),
            '--receipt',str(stage/'loader-receipt.json'),'--',*opts,'--logfile='+str(stage/'install.log')]
        with (stage/'install-bootstrap.log').open('x') as log:
            status=subprocess.run(offline_odoo(command),stdout=log,stderr=subprocess.STDOUT)
        write(stage/'install-status.json',{'exit_code':status.returncode,'all_products_operational':False,'production_changed':False})
        assert status.returncode==0, 'Inspect private guarded install log; no acceptance claimed'
        write(stage/'business-after-install.json',column_snapshot(database,columns))
        expression = ('import sys,json; sys.path.insert(0,' + repr(str(source/'tools/community')) + '); '
            'from postcheck_original_anchor import run; result=run(env,' + repr(str(stage))
            + ',database=' + repr(database) + ',reference=' + repr(reference)
            + ',capsule_sha256=' + repr(CAPSULE_SHA) + ',identity_sha256=' + repr(sha(stage/'identity-before.json'))
            + '); env.cr.commit(); open(' + repr(str(stage/'cohort-admission.json'))
            + ',"x").write(json.dumps(result,indent=2)); print("ORIGINAL_COHORT_PROBE_OK")')
        normal_opts=opts[:-2]  # ordinary CLI, no init/upgrade and no retention wrapper
        with (stage/'cohort-bootstrap.log').open('x') as log:
            status=subprocess.run(offline_odoo(normal+normal_opts+['--logfile='+str(stage/'cohort.log')]),
                input=expression,text=True,stdout=log,stderr=subprocess.STDOUT)
        assert status.returncode==0 and (stage/'cohort-admission.json').is_file(), 'Original cohort probe failed; inspect private evidence'
        (stage/'cohort-admission.json').chmod(0o600)
        write(stage/'business-after-cohort.json',column_snapshot(database,columns))
        write(stage/'identity-after.json',preservation.identity_contract(database))
        print('ORIGINAL_ANCHOR_COHORT_PROBED_REQUIRES_COMPLETE_PRESERVATION_REVIEW',flush=True)


if __name__=='__main__':main()
