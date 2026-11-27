"""Restore a private Steps task and document trial from the verified 168-module copy."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import tarfile

from load_steps_sales_extension import guarded_command
from restore_local_steps_expense_credit import DB, GUEST, HOST, PORT, call, pg, sql
from restore_local_steps_integrated import snapshot
from steps_project_release import MODULES, PACKAGE
from verify_converted_backup import check, hash_file
from verify_steps_support_backup import compressed


TOOLS = Path(__file__).resolve().parent
TARGET = 'COMMUNITY_STEPS_PROJECT_20261127U51Q'
PARENT = '288ff5e72369c9179736ca24179d66e29339745076115299b2fd069b41615a44'
META = {'ir_act_window','ir_cron_trigger','ir_model','ir_model_access','ir_model_constraint','ir_model_data',
        'ir_model_fields','ir_model_fields_selection','ir_model_relation','ir_module_module','ir_module_module_dependency',
        'ir_ui_menu','ir_ui_menu_group_rel','ir_ui_view','res_partner','res_country'}


def capture(database):
    return snapshot(database, socket_dir=GUEST/'socket', port_number=PORT, tools_root=GUEST/'tools', execute=call)


def inventory(folder):
    return {p.relative_to(folder).as_posix(): [p.stat().st_size,hash_file(p)] for p in folder.rglob('*') if p.is_file()}


def verify_addresses():
    script = """
import psycopg2
from contextlib import closing
opts=dict(host=host,port=port,user='postgres')
with closing(psycopg2.connect(dbname=base,**opts)) as original,closing(psycopg2.connect(dbname=changed,**opts)) as trial:
    for session in (original,trial):
        session.set_session(readonly=True,isolation_level='REPEATABLE READ')
    with original.cursor() as left,trial.cursor() as right:
        for table,audit in [('res_country',[]),('res_partner',['write_uid','write_date'])]:
            query='SELECT id,to_jsonb(t) FROM '+table+' t ORDER BY id'
            left.execute(query)
            right.execute(query)
            before=dict(left.fetchall())
            after=dict(right.fetchall())
            assert before.keys()==after.keys()
            for n,row in before.items():
                assert all(after[n][field]==v for field,v in row.items() if field not in audit)
        print(len(before))
"""
    prelude = f'host={str(GUEST/"socket")!r};port={PORT!r};base={DB!r};changed={TARGET!r}\n'
    out = call('postgres',['python3.10','-c',prelude+script],capture_output=True)
    return int(out.stdout)


def install(archive, parent, result):
    check(hash_file(archive)==PACKAGE and hash_file(parent/'checkpoint.json')==PARENT and
          sql('postgres','SHOW data_directory')==str(GUEST/'postgres/cluster'), 'wrong-project-trial-release')
    before, definitions = capture(DB)
    check(before == compressed(parent,'snapshot.json.gz'), 'changed-168-parent')
    folder = HOST/'project-qualification'
    guest = GUEST/folder.name
    folder.mkdir(exist_ok=True)
    marker = folder/'release.json'
    identity = {'database':TARGET,'parent':PARENT,'package':PACKAGE}
    exists = sql('postgres',f"SELECT COUNT(*) FROM pg_database WHERE datname='{TARGET}'") == '1'
    if not marker.exists():
        check(not exists and shutil.disk_usage(HOST).free > 1024**3, 'private-project-database-space-or-identity')
        marker.write_text(json.dumps(identity,sort_keys=True))
    check(json.loads(marker.read_bytes())==identity,'different-project-release')
    if not exists:
        pg('createdb','--template='+DB,'--owner=odoo',TARGET)
        check(capture(TARGET)==[before,definitions],'incorrect-project-base-copy')
    store = folder/'data/filestore'/TARGET
    stored = compressed(parent,'filestore.json.gz')
    if not store.exists():
        shutil.copytree(HOST/'data/filestore'/DB,store)
        for path in (folder/'data',*(folder/'data').rglob('*')):
            os.chown(path,61018,61018)
            path.chmod(0o700 if path.is_dir() else 0o600)
    check(inventory(store)==stored,'incorrect-project-filestore')
    (folder/'data/tmp').mkdir(exist_ok=True)
    os.chown(folder/'data/tmp',61018,61018)
    overlay = folder/'addons'/PACKAGE
    code = folder/'code'
    code.mkdir(exist_ok=True)
    for name in ('load_steps_sales_extension','preflight_original_history_storage','probe_steps_accounting_history',
                 'probe_steps_project_history','probe_steps_project_task_flow'):
        shutil.copyfile(TOOLS/(name+'.py'),code/(name+'.py'))
    files = {}
    with tarfile.open(archive) as tar:
        for member in tar:
            path = Path(member.name)
            check(not path.is_absolute() and len(path.parts)>=2 and '..' not in path.parts and
                  path.parts[0] in MODULES and member.isfile() and member.name not in files,'unexpected-project-addon-member')
            output = overlay/path
            output.parent.mkdir(parents=True,exist_ok=True)
            raw = tar.extractfile(member).read()
            if not output.exists():
                output.write_bytes(raw)
            check(output.resolve()==output and output.read_bytes()==raw,'different-project-provider-file')
            files[member.name] = path.parts[0]
    check({n:list(files.values()).count(n) for n in MODULES}==MODULES and
          {p.relative_to(overlay).as_posix() for p in overlay.rglob('*') if p.is_file()}==files.keys(),
          'incomplete-project-package')
    args = json.loads((HOST/'recovery-profile.json').read_bytes())
    check(args[args.index('-d')+1]==DB and '--no-http' in args and '--max-cron-threads=0' in args,'unexpected-project-launch')
    args = [a.replace(DB,TARGET).replace(str(GUEST/'data'),str(guest/'data')) for a in args]
    place, = [i for i,a in enumerate(args) if a.startswith('--addons-path=')]
    args[place] = '--addons-path='+str(guest/overlay.relative_to(folder))+','+args[place].split('=',1)[1]
    (folder/'args.json').write_text(json.dumps(args))
    installer = args.copy()
    installer.remove('shell')
    for module in MODULES:
        present = sql(TARGET,f"SELECT state FROM ir_module_module WHERE name='{module}'") == 'installed'
        switches = ['--stop-after-init','-u' if present else '-i',module]
        command = [str(v).replace(str(HOST),str(GUEST)) for v in guarded_command(installer+switches,folder,before)]
        with (folder/(module+'.log')).open('ab') as log:
            call('odoo',command,stdout=log,stderr=log)
    after, catalogue = capture(TARGET)
    changed = sorted(n for n,v in before['public_tables'].items() if after['public_tables'].get(n)!=v)
    check(set(changed)<=META and set(after['public_tables'])==set(before['public_tables'])|{'res_city'} and
          all(catalogue.get(n)==v for n,v in definitions.items()),'unexpected-project-business-or-schema-drift')
    check(inventory(store)==stored and capture(DB)==[before,definitions],'project-qualification-changed-the-parent')
    providers = json.loads(sql(TARGET,"SELECT json_object_agg(name,json_build_array(latest_version,license)) FROM ir_module_module WHERE state='installed'"))
    expected = json.loads((parent/'providers.json').read_bytes())
    check(set(providers)==set(expected)|set(MODULES) and all(providers[n]==ver for n,ver in expected.items()),'incorrect-project-providers')
    summary = {'database':TARGET,'modules':len(providers),'code_files':len(files),'files':len(stored),
               'package':PACKAGE,'parent':PARENT,'changed_tables':changed,'addresses_preserved':verify_addresses(),
               'preserved_sql_objects':len(definitions),'new_sql_objects':len(catalogue)-len(definitions)}
    result.write_text(json.dumps(summary,sort_keys=True))
    print(json.dumps(summary))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('archive','parent','result'):
        parser.add_argument(arg,type=Path)
    opts = parser.parse_args()
    with open('/dev/shm/steps-shared-qa-restore.lock','a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        install(opts.archive,opts.parent,opts.result)
