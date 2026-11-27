"""Install the report provider on the existing RAM trial A, using the admitted trial B as its control."""
import argparse
import fcntl
import hashlib
import json
import os
import tarfile
import tempfile
from pathlib import Path
import shutil
import subprocess

from compare_cerro_studio_receipts import compare, receipt
from build_cerro_verified_172 import build
from prepare_cerro_wsl_packing_cold import FINAL, prepare

RAM=Path('/dev/shm/steps-cerro-u46')
DB='COMMUNITY_CERRO_BOM_PACKING_20261127U46A'
SOURCE='COMMUNITY_CERRO_BOM_PACKING_20261127U46B'
MODULE='step_cerro_pack_reports'
HERE=Path(__file__).parent


def run(executor,artifacts,cold):
    db=FINAL if cold else DB
    work=RAM/('packing-c' if cold else 'packing')
    accepted=RAM/'packing-b'
    assert hashlib.sha256((accepted/'accepted-picking.json').read_bytes()).hexdigest()=='501aa3df9576c73c74b29c417d1912035079fb9f7961bb0ef98e808fd02b5bd7'
    if cold:
        with open('/dev/shm/steps-shared-qa-restore.lock','a') as shared:
            fcntl.flock(shared,fcntl.LOCK_EX)
            prepare(executor,FINAL)
        work.mkdir(mode=0o755,exist_ok=True)
        plan=json.loads((accepted/'original-required.json').read_bytes())
        assert plan['database']==SOURCE and len(plan['fields'])==29
        plan['database']=db
        (work/'original-required.json').write_text(json.dumps(plan,sort_keys=True))
        inventory=json.loads((artifacts/'COMMUNITY_CERRO_BOM_CONTRACTS_20261127U44M-inventory').read_bytes())['objects']
        assert len(inventory)==677
        target=work/'data/filestore'/db
        target.mkdir(parents=True,exist_ok=True)
        for folder in (work/'data',work/'data/filestore',target):
            os.chown(folder,61018,61018)
            folder.chmod(0o700)
        for local,(checksum,size) in inventory.items():
            src=accepted/'data/filestore'/SOURCE/local
            dst=target/local
            dst.parent.mkdir(exist_ok=True)
            os.chown(dst.parent,61018,61018)
            if not dst.exists():
                shutil.copyfile(src,dst)
            assert dst.stat().st_size==size and src.stat().st_ino!=dst.stat().st_ino and hashlib.sha1(dst.read_bytes()).hexdigest()==checksum
            os.chown(dst,61018,61018)
            dst.chmod(0o600)
    assert json.loads((work/'original-required.json').read_bytes())['database']==db
    report=RAM/('reports-c' if cold else 'reports')
    report.mkdir(mode=0o755,exist_ok=True)
    def run_as(user,args,body=None,path=None):
        cmd=['python3',str(executor),'--user',user,'--',*map(str,args)]
        r=subprocess.run(cmd,input=body,capture_output=True)
        if path:
            (report/path).write_bytes(r.stdout+r.stderr)
        if r.returncode:
            raise RuntimeError((r.stdout+r.stderr).decode(errors='replace')[-1200:])
        return r.stdout.decode()
    pgargs=['-h',RAM/'socket','-p','55443']
    def sql(db,query):
        return run_as('postgres',['psql',*pgargs,'-XAt','-v','ON_ERROR_STOP=1','-d',db,'-c',query]).strip()
    seal=report/'previous-dump.json'
    previous=RAM/'pg/trial-a-before-reports.dump'
    if not cold and not seal.exists():
        assert sql(DB,"select count(*) from ir_module_module where state='installed'")=='190'
        run_as('postgres',['pg_dump',*pgargs,'--format=custom','-f',previous,DB])
        seal.write_text(json.dumps(dict(db=DB,sha256=hashlib.sha256(previous.read_bytes()).hexdigest()),sort_keys=True))
    if not cold:
        assert json.loads(seal.read_bytes())==dict(db=DB,sha256=hashlib.sha256(previous.read_bytes()).hexdigest())
    archives={}
    for profile,mod in [('picking','step_cerro_picking_list_history'),('pack_reports',MODULE)]:
        addon=report/'addons'/mod
        addon.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=report) as tempdir:
            archive=Path(tempdir)/'tested.tar'
            archives[mod]=build(HERE.parents[1],archive,profile)
            with tarfile.open(archive) as pack:
                for member in pack:
                    path=Path(member.name)
                    assert member.isfile() and path.parent==Path(mod) and path.suffix=='.py'
                    (addon/path.name).write_bytes(pack.extractfile(member).read())
    code=report/'code'
    code.mkdir(exist_ok=True)
    for name in ('load_cerro_catalog_contracts.py','probe_cerro_pack_report_rows.py','probe_cerro_studio_fullread.py',
                 'probe_cerro_studio_views.py','probe_cerro_picking_lists.py','probe_cerro_studio_navigation.py','probe_cerro_studio_client.py',
                 'check_cerro_pack_schema.py','check_cerro_local_catalogue.py','audit_cerro_original_schema.py'):
        shutil.copyfile(HERE/name,code/name)
    opts=['-d',db,'--db-filter=^'+db+'$','--db_user=dev_odoo18','--db_host='+str(RAM/'socket'),'--db_port=55443',
          '--addons-path='+str(report/'addons')+','+str(accepted/'addons')+',/work/cerro-pg/source/addons','--data-dir='+str(work/'data'),
          '--logfile='+str(work/'data/report-odoo.log'),'--no-http','--workers=0','--max-cron-threads=0',
          '--stop-after-init','--without-demo=all','--load=base,web']
    extra=['--final'] if cold else []
    seq=['/usr/bin/python3.10',code/'check_cerro_pack_schema.py',*extra]
    intermediate=report/'accepted-190.json'
    if cold and not intermediate.exists():
        assert sql(db,"select count(*) from ir_module_module where state='installed'") in ('189','190')
        for flag in ('-i','-u'):
            run_as('odoo',['/usr/bin/python3.10',code/'load_cerro_catalog_contracts.py','--cerro-local-qa',*opts,flag,'step_cerro_picking_list_history'],path='190-'+flag[1:]+'.log')
            run_as('postgres',[*seq,'--at190'],path='190-'+flag[1:]+'-schema.json')
        script="import sys,json\nsys.path.insert(0,"+repr(str(code))+")\nfrom probe_cerro_picking_lists import exercise,search_cases\nprint('PICKING_USER',json.dumps(exercise(env),sort_keys=True))\nprint('PICKING_MIXED',json.dumps(search_cases(env),sort_keys=True))\n"
        run_as('odoo',['/usr/bin/python3.10','/work/sys-fg-code/odoo-bin','shell',*opts],script.encode(),'190-user.log')
        for marker,name in [('PICKING_USER','native-picking-search-u46.json'),('PICKING_MIXED','native-picking-mixed-search-u46.json')]:
            assert receipt(report/'190-user.log',marker)==json.loads((artifacts/name).read_bytes())
        intermediate.write_text(json.dumps(dict(package=archives['step_cerro_picking_list_history'],seed=json.loads((RAM/'source-dump.json').read_bytes())['sha256'],
              baseline=hashlib.sha256((report/'190-i-schema.json').read_bytes()).hexdigest()),sort_keys=True))
    if cold:
        mark=json.loads(intermediate.read_bytes())
        assert mark['package']==archives['step_cerro_picking_list_history']
        assert mark['seed']==json.loads((RAM/'source-dump.json').read_bytes())['sha256']
    installed=sql(db,"select state from ir_module_module where name='"+MODULE+"'")=='installed'
    for flag in (('-u',) if installed else ('-i','-u')):
        run_as('odoo',['/usr/bin/python3.10',code/'load_cerro_catalog_contracts.py','--cerro-local-qa',*opts,flag,MODULE],path=flag[1:]+'.log')
        assert sql(db,"select state||'|'||latest_version from ir_module_module where name='"+MODULE+"'")=='installed|18.0.1.0.0'
        run_as('postgres',seq,path=flag[1:]+'-schema.json')
    body="import sys,json\nsys.path.insert(0,"+repr(str(code))+")\n"
    body+="from probe_cerro_pack_report_rows import capture,controls,history_scope\nprint('PACK_ROWS',json.dumps(capture(env),sort_keys=True))\nprint('PACK_CONTROLS',json.dumps(controls(env),sort_keys=True))\nprint('REPORT_SCOPE',json.dumps(history_scope(env),sort_keys=True))\n"
    body+="from probe_cerro_picking_lists import exercise,search_cases\nprint('PICKING_USER',json.dumps(exercise(env),sort_keys=True))\nprint('PICKING_MIXED',json.dumps(search_cases(env),sort_keys=True))\n"
    body+="from probe_cerro_studio_fullread import capture as fullread\nfrom probe_cerro_studio_navigation import capture as routes\nfrom probe_cerro_studio_client import capture as client\nprint('PACK_VIEWS',json.dumps(dict(fullread=fullread(env),routes=routes(env),client=client(env)),sort_keys=True))\nenv.cr.rollback()\n"
    before=json.loads(run_as('postgres',[*seq,'sequences']))
    try:
        run_as('odoo',['/usr/bin/python3.10','/work/sys-fg-code/odoo-bin','shell',*opts],body.encode(),'user.log')
    finally:
        restored=json.loads(run_as('postgres',[*seq,'restore-sequences'],json.dumps(before).encode()))
        assert json.loads(run_as('postgres',[*seq,'sequences']))==before
    assert receipt(report/'user.log','REPORT_SCOPE')==dict(read=True,denied=['create','write','unlink'])
    for marker,reference in [('PICKING_USER','native-picking-search-u46.json'),('PICKING_MIXED','native-picking-mixed-search-u46.json')]:
        assert receipt(report/'user.log',marker)==json.loads((artifacts/reference).read_bytes())
    positive=artifacts/'native-pack-report-controls-u46.json'
    assert hashlib.sha256(positive.read_bytes()).hexdigest()=='4bad66f2d093e0fc7faddfb6602d113d61041d8479d6e1361e5861b0cfcc40e6'
    assert receipt(report/'user.log','PACK_CONTROLS')==json.loads(positive.read_bytes())
    native=artifacts/'native-pack-orders-u46.json'
    assert hashlib.sha256(native.read_bytes()).hexdigest()=='eb3f396575eea81656c1c21bc55b18d35faaf30b35127dbc29ee728572ff1ec7'
    assert receipt(report/'user.log','PACK_ROWS')==json.loads(native.read_bytes())
    candidate=receipt(report/'user.log','PACK_VIEWS')
    matrix=compare(receipt(artifacts/'native-full.log','CERRO_FULL_READ'),receipt(artifacts/'native-routes.log','CERRO_FULL'),candidate)
    earlier=json.loads((accepted/'accepted-picking.json').read_bytes())['matrix']
    assert all(set(earlier[k])<=set(matrix[k]) for k in ('original_routes','matching_full_record','matching_studio_values'))
    expected={'odoo_studio_step_pac_830a88ea-ec01-461a-bdae-fa936e0906d6',
              'odoo_studio_step_pac_30c94bad-4a0d-482d-9bf6-49393b7cd896',
              'odoo_studio_packing__86a22479-165a-420c-90f8-8b94f530c935'}
    assert expected<=set(matrix['matching_full_record'])
    assert len(matrix['original_routes'])==len(matrix['matching_studio_values'])==23
    assert len(matrix['matching_full_record'])>=21
    out=dict(archives=archives,cold=cold,matrix=matrix,pointers_restored=restored,scope=receipt(report/'user.log','REPORT_SCOPE'),
             picking_reference=hashlib.sha256((artifacts/'native-picking-search-u46.json').read_bytes()).hexdigest(),
             mixed_reference=hashlib.sha256((artifacts/'native-picking-mixed-search-u46.json').read_bytes()).hexdigest(),positive_reference=hashlib.sha256(positive.read_bytes()).hexdigest(),history_reference=hashlib.sha256(native.read_bytes()).hexdigest(),schema=json.loads((report/'u-schema.json').read_bytes()))
    (report/'accepted.json').write_text(json.dumps(out,sort_keys=True))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--executor',required=True,type=Path)
    p.add_argument('--artifacts',required=True,type=Path)
    p.add_argument('--cold-chain',action='store_true')
    args=p.parse_args()
    with (RAM/'reports.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        run(args.executor,args.artifacts,args.cold_chain)
