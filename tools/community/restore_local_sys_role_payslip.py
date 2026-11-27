"""Restore the sealed SyS payroll print checkpoint with its original code and 2,708 physical files."""
import argparse
import fcntl
import gzip
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile

from admit_sys_role_payslip_print import PACKAGE, STAGE, WORK
from restore_local_steps_expense_credit import GUEST, HOST, PORT, call, pg, sql
from seal_local_sys_193 import MEM, psql
from verify_converted_backup import check, hash_file


HERE=Path(__file__).resolve().parent
DB='COMMUNITY_SYS_FINAL_PRINT_RECOVERY_20261127U51S'
SOURCE='COMMUNITY_SYS_PREVIRED_COHORT_20261127U49E'
INDEX='a171f16a6254ecf4f6392823b8d536bc5e7d06e36d77f96a07662fd1a574ec32'
CUSTODY='b9cd49e92efb966a01b9051f4647b8de7ebe2bf067089782b4b999e73074741e'
NEGATIVE_NET='246f45bee249a4a674b076de75669561499dcd9d1d8492c77a4877f4abda6dde'


def capture():
    body = """
import json,sys,psycopg2
sys.path.insert(0,'/dev/shm/sys-fg-193/tools')
from compare_sys_full_restore import snapshot
from guard_sys_original_catalogue import SQL,digest
with psycopg2.connect(dbname=db,host=sock,port=port,user='postgres') as cx:
    cx.set_session(readonly=True)
    with cx.cursor() as cr:
        cr.execute('SET LOCAL search_path=pg_catalog,public')
        cr.execute(SQL)
        catalogue=digest(cr.fetchone()[0])
print(json.dumps({'catalogue':catalogue,'snapshot':snapshot(db, socket_dir=sock,port=port)}))
"""
    values=f'db={DB!r};sock={str(GUEST/"socket")!r};port={PORT!r}\n'
    return json.loads(call('postgres',['python3.10','-c',values+body],capture_output=True).stdout)


def verify_code(archive, dest, checksum, expected_files):
    check(hash_file(archive)==checksum, 'unexpected-payroll-provider-archive')
    with tarfile.open(archive) as package:
        check(len(package.getmembers())==expected_files, 'incomplete-payroll-provider-archive')
        for item in package:
            path=Path(item.name)
            check(item.isfile() and not path.is_absolute() and '..' not in path.parts and
                  (dest/path).resolve(strict=True)==dest/path and
                  (dest/path).read_bytes()==package.extractfile(item).read(), 'different-valid-payroll-print-provider')


def restore(checkpoint, kit, capsule, output):
    check(hash_file(checkpoint/'checkpoint.json')==INDEX and hash_file(kit/'release.json')==CUSTODY,
          'wrong-payroll-print-checkpoint')
    proof=json.loads((checkpoint/'checkpoint.json').read_bytes())
    check(proof['database']==SOURCE and proof['providers']==194 and proof['package']==PACKAGE,'different-payroll-source')
    for name,(size,checksum) in proof['files'].items():
        file=checkpoint/name
        check(Path(name).name==name and hash_file(file)==checksum and file.stat().st_size==size,'broken-payroll-print-checkpoint')
    source=json.loads(gzip.decompress((checkpoint/'snapshot.json.gz').read_bytes()))
    tree=json.loads(gzip.decompress((checkpoint/'filestore.json.gz').read_bytes()))
    providers=json.loads((checkpoint/'providers.json').read_bytes())
    custody=json.loads((kit/'release.json').read_bytes())
    for name,checksum in custody['files'].items():
        check(Path(name).name==name and hash_file(kit/name)==checksum,'unexpected-print-kit-piece')
    verify_code(kit/('step_sys_payslip_print-'+PACKAGE+'.tar'),STAGE/'addons'/PACKAGE,PACKAGE,4)
    verify_code(WORK/('negative-net-'+NEGATIVE_NET+'.tar'),WORK/'overlay',NEGATIVE_NET,11)
    path=HOST/'sys-print-recovery'
    guest=GUEST/path.name
    path.mkdir(exist_ok=True,mode=0o755)
    marker=path/'checkpoint'
    exists=sql('postgres',f"SELECT COUNT(*) FROM pg_database WHERE datname='{DB}'")=='1'
    if not marker.exists():
        check(not exists and shutil.disk_usage(HOST).free>2*1024**3,'private-payroll-restore-capacity')
        marker.write_text(INDEX)
    check(marker.read_text()==INDEX,'wrong-payroll-database-marker')
    options="""SELECT DISTINCT pg_get_userbyid(refobjid) FROM pg_shdepend
               WHERE dbid=(SELECT oid FROM pg_database WHERE datname=current_database()) AND refclassid='pg_authid'::regclass"""
    roles=psql(options,SOURCE).splitlines()
    for role in roles:
        check(re.fullmatch(r'[a-z_][a-z0-9_]*',role),'unexpected-payroll-role')
        if not sql('postgres',f"SELECT 1 FROM pg_roles WHERE rolname='{role}'"):
            check(role not in ('postgres','odoo'),'private-postgres-role-missing')
            sql('postgres',f'CREATE ROLE "{role}" NOLOGIN')
    if not exists:
        pg('createdb','--template=template0','--owner=odoo','--encoding=UTF8','--lc-collate=C','--lc-ctype=C.UTF-8',DB)
    if sql(DB,"SELECT count(*) FROM pg_tables WHERE schemaname='public'")=='0':
        with (checkpoint/'source.dump').open('rb') as archive,(path/'restore.log').open('wb') as log:
            pg('pg_restore','--exit-on-error','--single-transaction','--no-tablespaces','-d',DB,stdin=archive,stdout=log,stderr=log)
    check(capture()==source,'restored-payroll-catalogue-rows-or-contadores-differ')
    store=path/'data/filestore'/DB
    if not store.exists():
        shutil.copytree(WORK/'data/filestore'/SOURCE,store)
        for item in (path/'data',*(path/'data').rglob('*')):
            os.chown(item,61018,61018)
            item.chmod(0o700 if item.is_dir() else 0o600)
    def physical():
        return {f.relative_to(store).as_posix():[f.stat().st_size,hash_file(f)] for f in store.rglob('*') if f.is_file()}
    check(physical()==tree,'restored-payroll-physical-files-differ')
    profile=path/'odoo.conf'
    profile.write_text(f'[options]\ndb_user=odoo\nlist_db=False\ndb_host={GUEST/"socket"}\ndb_port={PORT}\nlog_level=warn\n')
    roots = json.loads((STAGE/'roots.json').read_bytes())
    check(roots==[str(STAGE/'addons'/PACKAGE),str(WORK/'overlay'),str(MEM/'overlay'),'/work/sys-fg-code/addons',
                  '/work/sys-fg-code/odoo/addons'],'wrong-payroll-registered-runtime')
    command = [sys.executable,str(HERE/'run_focal_print_command.py'),'--steps-expense-recovery','--sys-payslip-form',
               '--loopback','--user','odoo','--','python3.10','/work/sys-fg-code/odoo-bin','shell','-c',str(guest/profile.name),
               '-d',DB,'--db-filter=^'+DB+'$','--addons-path='+','.join(roots),'--data-dir='+str(guest/'data'),
               '--load=base,web','--workers=0','--max-cron-threads=0','--no-http','--stop-after-init']
    control=json.loads(capsule.read_bytes())
    active_check=("seen={m.name:[m.latest_version,m.license] for m in env['ir.module.module'].search([('state','=','installed')])}\n"
                  f"assert seen=={providers!r}\n")
    program=(HERE/'probe_sys_role_payslip_pdf.py').read_text(encoding='utf-8')
    counts=[]
    for boot in (1,2):
        details=path/f'boot-{boot}'
        details.mkdir(mode=0o700)
        os.chown(details,61018,61018)
        input_code=active_check+program+f"\nprint('SYS_RESTORED '+json.dumps(run(env,{control!r},{str(guest/details.name)!r})))\n"
        proc=subprocess.run(command,input=input_code.encode(),capture_output=True)
        (details/'stderr.log').write_bytes(proc.stderr)
        observed=[json.loads(r[13:]) for r in proc.stdout.splitlines() if r.startswith(b'SYS_RESTORED ')]
        check(proc.returncode==0 and len(observed)==1 and len(observed[0]['documents'])==10
              and observed[0]['original_attachments']==8,'cold-payroll-form-or-pdf-failed')
        check(capture()==source and physical()==tree,'cold-payroll-render-modified-source')
        counts.append(len(observed[0]['documents']))
    output.write_text(json.dumps({'recovery':DB,'index':INDEX,'providers':len(providers),'rows':proof['rows'],
                      'sequences':proof['sequences'],'files':len(tree),'reads_per_start':counts},sort_keys=True))
    print(hash_file(output))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('checkpoint','kit','capsule','output'):
        parser.add_argument(name,type=Path)
    args=parser.parse_args()
    with open('/dev/shm/steps-shared-qa-restore.lock','a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        restore(args.checkpoint,args.kit,args.capsule,args.output)
