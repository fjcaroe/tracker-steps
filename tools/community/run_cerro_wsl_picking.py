"""Install, upgrade and compare the two original Cerro transfer lists on a private PG12 copy."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from build_cerro_verified_172 import build
from prepare_cerro_wsl_pilots import WORK, INSIDE
from prepare_cerro_wsl_packing_cold import RAM, prepare as prepare_cold
from compare_cerro_studio_receipts import receipt, compare


SOURCE = 'COMMUNITY_CERRO_BOM_CONCEPTS_20261127U45P'
BENCH = 'COMMUNITY_CERRO_BOM_PACKING_20261127U46A'
COLD = 'COMMUNITY_CERRO_BOM_PACKING_20261127U46B'
MODULE = 'step_cerro_picking_list_history'
PRIOR = '50849918f3750c2dc7891d7e1b964f351c2526750f238d3249159f60614a253e'
TOOLS = Path(__file__).parent


def run(executor, artifacts, stage, cold):
    assert os.getuid()==0
    if not cold:
        assert shutil.disk_usage('/mnt/c').free>512*1024**2
    DB=COLD if cold else BENCH
    package=RAM/'packing-b' if cold else WORK/'packing'
    if cold:
        prepare_cold(executor)
    package.mkdir(mode=0o755,exist_ok=True)
    source = WORK/'concepts'
    assert hashlib.sha256((source/'accepted-concepts.json').read_bytes()).hexdigest()==PRIOR
    original = json.loads((source/'accepted-concepts.json').read_bytes())
    def execute(user, args, body=None, output=None):
        inv = ['python3',str(executor),'--user',user,'--',*map(str,args)]
        proc = subprocess.run(inv,input=body,capture_output=True)
        if output:
            (package/output).write_bytes(proc.stdout+proc.stderr)
        if proc.returncode:
            raise ValueError((proc.stdout+proc.stderr).decode(errors='replace')[-1300:])
        return proc.stdout.decode()
    socket=RAM/'socket' if cold else INSIDE/'socket'
    port='55443' if cold else '55442'
    dbopts=['-h',socket,'-p',port]
    def sql(db, query):
        return execute('postgres',['psql',*dbopts,'-XAt','-v','ON_ERROR_STOP=1','-d',db,'-c',query]).strip()
    owner = sql('postgres',"SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='"+DB+"'")
    marker = package/'clone-source.json'
    if not marker.exists():
        assert not owner or cold
        marker.write_text(json.dumps(dict(source=SOURCE,receipt=PRIOR,trial=DB),sort_keys=True))
    assert json.loads(marker.read_bytes())==dict(source=SOURCE,receipt=PRIOR,trial=DB)
    if not owner:
        assert stage!='compare' and shutil.disk_usage('/mnt/c').free>2*1024**3
        execute('postgres',['createdb',*dbopts,'--owner=dev_odoo18','--template='+SOURCE,DB])
    else:
        assert owner=='dev_odoo18'
    store = source/'data/filestore'/SOURCE
    data = package/'data'
    target = data/'filestore'/DB
    target.mkdir(exist_ok=True, parents=True)
    for path in (data,data/'filestore',target):
        os.chown(path,61018,61018)
        path.chmod(0o700)
    inventory = json.loads((artifacts/'COMMUNITY_CERRO_BOM_CONTRACTS_20261127U44M-inventory').read_bytes())['objects']
    assert len(inventory)==original['objects']==677
    for name,(checksum,size) in inventory.items():
        src, dst = store/name, target/name
        dst.parent.mkdir(exist_ok=True)
        os.chown(dst.parent,61018,61018)
        if not dst.exists():
            assert stage!='compare'
            shutil.copyfile(src,dst)
        assert src.stat().st_ino!=dst.stat().st_ino and dst.stat().st_size==size and hashlib.sha1(dst.read_bytes()).hexdigest()==checksum
        os.chown(dst,61018,61018)
        dst.chmod(0o600)
    plan=json.loads((source/'original-required.json').read_bytes())
    assert plan['database']==SOURCE and len(plan['fields'])==29
    plan['database']=DB
    (package/'original-required.json').write_text(json.dumps(plan,sort_keys=True))
    addon=package/'addons'/MODULE
    import tarfile
    import tempfile
    archive_sha=json.loads((TOOLS/'cerro_studio_picking_receipt.json').read_bytes())['archive_sha256']
    with tempfile.TemporaryDirectory(dir=package) as tmp:
        archive=Path(tmp)/'qualified.tar'
        assert build(TOOLS.parents[1],archive,'picking')==archive_sha
        addon.mkdir(parents=True,exist_ok=True)
        with tarfile.open(archive) as bundle:
            for record in bundle.getmembers():
                member=Path(record.name)
                assert record.isfile() and member.parent==Path(MODULE) and member.suffix=='.py'
                (addon/member.name).write_bytes(bundle.extractfile(record).read())
    assert {p.name for p in addon.iterdir() if p.is_file()}=={'__init__.py','__manifest__.py','models.py','hooks.py'}
    code=package/'code'
    code.mkdir(exist_ok=True)
    for name in ('load_cerro_catalog_contracts.py','check_cerro_local_catalogue.py','audit_cerro_original_schema.py',
                 'probe_cerro_picking_lists.py','probe_cerro_studio_fullread.py','probe_cerro_studio_views.py',
                 'probe_cerro_studio_client.py','probe_cerro_studio_navigation.py'):
        shutil.copyfile(TOOLS/name,code/name)
    inner = str(package) if cold else '/work/cerro-pg/packing'
    opts=['-d',DB,'--db-filter=^'+DB+'$','--db_user=dev_odoo18','--db_host='+str(socket),'--db_port='+port,
          '--addons-path='+inner+'/addons,/work/cerro-pg/source/addons','--data-dir='+inner+'/data','--logfile='+inner+'/data/odoo.log',
          '--load=base,web','--no-http','--workers=0','--max-cron-threads=0','--stop-after-init','--without-demo=all']
    checks=['/usr/bin/python3.10',inner+'/code/check_cerro_local_catalogue.py','--packing'] + (['--cold'] if cold else [])
    if stage!='compare':
        for flag,phase in [('-i','install'),('-u','upgrade')]:
            execute('odoo',['/usr/bin/python3.10',inner+'/code/load_cerro_catalog_contracts.py','--cerro-local-qa',*opts,flag,MODULE],
                    output=phase+'.log')
            assert sql(DB,"SELECT state||'|'||latest_version FROM ir_module_module WHERE name='"+MODULE+"'")=='installed|18.0.1.0.0'
            result=execute('postgres',checks,output=phase+'-schema.json')
            assert json.loads(result)['census']==[190,0,0]
    if stage=='install':
        return
    shell=['/usr/bin/python3.10','/work/sys-fg-code/odoo-bin','shell',*opts]
    before=json.loads(execute('postgres',[*checks,'sequences']))
    base="import sys,json\nsys.path.insert(0,"+repr(inner+'/code')+")\n"
    try:
        execute('odoo',shell,(base+"from probe_cerro_picking_lists import exercise,search_cases\nprint('PICKING_USER',json.dumps(exercise(env),sort_keys=True))\nprint('PICKING_MIXED',json.dumps(search_cases(env),sort_keys=True))").encode(),
                'picking-user.log')
    finally:
        execute('postgres',[*checks,'restore-sequences'],json.dumps(before).encode())
        assert json.loads(execute('postgres',[*checks,'sequences']))==before
    body="""from probe_cerro_studio_fullread import capture as fullread
from probe_cerro_studio_navigation import capture as routes
from probe_cerro_studio_client import capture as client
print('PICKING_VIEWS',json.dumps(dict(fullread=fullread(env),routes=routes(env),client=client(env)),sort_keys=True))
env.cr.rollback()
"""
    execute('odoo',shell,(base+body).encode(),'picking-views.log')
    candidate=receipt(package/'picking-views.log','PICKING_VIEWS')
    result=compare(receipt(artifacts/'native-full.log','CERRO_FULL_READ'),receipt(artifacts/'native-routes.log','CERRO_FULL'),candidate)
    for name in ('matching_full_record','matching_studio_values','original_routes'):
        assert set(original['matrix'][name])<=set(result[name]), name
    aliases=['odoo_studio_stock_pi_9c7343b2-f76b-4e92-a062-e7dc0e3dc55b', 'odoo_studio_stock_pi_37167c21-3110-45c0-8fcd-9f89ded2bcc8']
    assert set(aliases)<=set(result['matching_full_record']) and {'5187','5244'}<=set(result['original_routes']), result
    reference=artifacts/'native-picking-search-u46.json'
    assert hashlib.sha256(reference.read_bytes()).hexdigest()=='35c8b598ffe9ee8582991468b2ecaabacc671672707fdf3fefdedde51fd00962'
    assert receipt(package/'picking-user.log','PICKING_USER')==json.loads(reference.read_bytes())
    mixed=artifacts/'native-picking-mixed-search-u46.json'
    assert hashlib.sha256(mixed.read_bytes()).hexdigest()=='8c138bcfadb1d9b8b12b37bb15c8aa4fc31599af9e9ae12d9602f396b1443fa5'
    assert receipt(package/'picking-user.log','PICKING_MIXED')==json.loads(mixed.read_bytes())
    report=dict(mixed_reference=hashlib.sha256(mixed.read_bytes()).hexdigest(),reference=hashlib.sha256(reference.read_bytes()).hexdigest(),matrix=result,source=PRIOR,
                package_sha256=archive_sha,
                schema=json.loads((package/'upgrade-schema.json').read_bytes()),objects=len(inventory),sequences=len(before))
    (package/'accepted-picking.json').write_text(json.dumps(report,sort_keys=True))
    print(hashlib.sha256((package/'accepted-picking.json').read_bytes()).hexdigest())


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executor',required=True,type=Path)
    parser.add_argument('--artifacts',required=True,type=Path)
    parser.add_argument('--stage',choices=('install','compare','all'),default='all')
    parser.add_argument('--cold',action='store_true')
    args=parser.parse_args()
    with (WORK/'packing.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        run(args.executor,args.artifacts,args.stage,args.cold)
