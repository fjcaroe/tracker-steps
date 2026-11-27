"""Qualify first install, upgrade and accounting operations in a private replica of the signed Cerro receipt profile."""
import argparse
from datetime import date
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

from build_cerro_verified_172 import build
from compare_cerro_studio_receipts import compare, receipt
from prepare_cerro_wsl_packing_cold import RAM
from run_cerro_receipt_flow import digest, stage

HERE=Path(__file__).parent
CONTROL='COMMUNITY_CERRO_BOM_PACKING_20261127U46D'
TRIAL='COMMUNITY_CERRO_BOM_PACKING_20261127U46A'
MODULE='step_cerro_contact_followup'
CONTACT='odoo_studio_res_part_47b48baf-5b77-4192-857b-fed73051f3c7'
REFERENCES={
    'properties':('native-followup-properties-u46.json','8421dddd45f182e381e1475bbb3da72bcb39b21b268776a096fdc19f9c92899b'),
    'cases':('native-followup-cases-u46.json','2673f74b2c2f239d94e0ba1dc874df6a69b089489e08e6e618522e53f5c7f665'),
    'mix':('native-followup-combinations-u46.json','f01de87a37cc1a7c68141bd884acf7934a364858e0d52c37f0fb7858c5d79a4f'),
    'changes':('native-followup-changes-u46.json','3b4b7739ee2231b9ce2246cf42c267f478fd86f31b7bf2c83e25a1057331cc9a'),
    'filters':('native-followup-request-filters-u46.json','0879d1ab33232cefefc547426b4217f4202aa95ee183e94179f4346b4fe3f900'),
}


def relative_dates(result):
    if 'data' in result:
        return dict(result,data=relative_dates(result['data']))
    if 'as_of' not in result:
        return result
    baseline=date.fromisoformat(result['as_of'])
    def row(value):
        return {key:(date.fromisoformat(item)-baseline).days if key in ('followup_next_action_date','next') and item else item
                for key,item in value.items()}
    return {**result,'as_of':'comparison day','cases':{key:row(value) for key,value in result['cases'].items()}}


def run(executor,art):
    source=RAM/'packing-receipt'
    control=source/'accepted-receipt.json'
    assert digest(control)=='f84eb7d6dc2ae5708642815f123113fc259c2e6c63ddde468f1bc9e785df00a7'
    previous=json.loads(control.read_bytes())
    work=RAM/'packing'
    work.mkdir(exist_ok=True)
    ws=work/'followup'
    ws.mkdir(exist_ok=True)
    socket=RAM/'socket'
    def call(user,args,content=None,log=None):
        reply=subprocess.run(['python3',str(executor),'--user',user,'--',*map(str,args)],input=content,capture_output=True)
        if log:
            path=ws/log
            path.write_bytes(reply.stdout+reply.stderr)
            path.chmod(0o600)
        if reply.returncode:
            raise RuntimeError((reply.stdout+reply.stderr).decode(errors='replace')[-1000:])
        return reply.stdout.decode()
    def sql(db,q):
        return call('postgres',['psql','-h',socket,'-p','55443','-XAt','-v','ON_ERROR_STOP=1','-d',db,'-c',q]).strip()
    with open('/dev/shm/steps-shared-qa-restore.lock','a') as restore:
        fcntl.flock(restore,fcntl.LOCK_EX)
        if not sql('postgres',"SELECT 1 FROM pg_database WHERE datname='"+TRIAL+"'"):
            call('postgres',['createdb','-h',socket,'-p','55443','--owner=dev_odoo18','--template='+CONTROL,TRIAL])
    assert sql('postgres',"SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='"+TRIAL+"'")=='dev_odoo18'
    target=work/'data/filestore'/TRIAL
    target.mkdir(parents=True,exist_ok=True)
    for folder in [work/'data',target.parent,target]:
        os.chown(folder,61018,61018)
        folder.chmod(0o700)
    inventory=json.loads((art/'COMMUNITY_CERRO_BOM_CONTRACTS_20261127U44M-inventory').read_bytes())['objects']
    assert len(inventory)==677
    for name,(checksum,size) in inventory.items():
        original=source/'data/filestore'/CONTROL/name
        dst=target/name
        dst.parent.mkdir(exist_ok=True)
        os.chown(dst.parent,61018,61018)
        if not dst.exists():
            shutil.copyfile(original,dst)
        assert dst.stat().st_ino!=original.stat().st_ino and dst.stat().st_size==size and hashlib.sha1(dst.read_bytes()).hexdigest()==checksum
        os.chown(dst,61018,61018)
        dst.chmod(0o600)
    required=json.loads((source/'original-required.json').read_bytes())
    assert required['database']==CONTROL and len(required['fields'])==29
    required['database']=TRIAL
    (work/'original-required.json').write_text(json.dumps(required,sort_keys=True))
    base=ws/'addons'
    base.mkdir(exist_ok=True)
    code=ws/'code'
    code.mkdir(exist_ok=True)
    for n in ('load_cerro_catalog_contracts','check_cerro_followup_catalogue','check_cerro_receipt_catalogue','check_cerro_pack_schema',
              'check_cerro_local_catalogue','audit_cerro_original_schema','probe_cerro_studio_fullread','probe_cerro_studio_navigation',
              'probe_cerro_studio_client','probe_cerro_studio_views','probe_cerro_contact_followup','probe_cerro_followup_cases',
              'probe_cerro_followup_filters','probe_cerro_reception_flow','probe_cerro_receipt_stock','probe_cerro_followup_properties'):
        shutil.copyfile(HERE/(n+'.py'),code/(n+'.py'))
    assert stage('picking',base)==previous['archives']['picking']
    assert stage('receipt_flow',base)==previous['archives']['receipt_flow']
    flags=['-d',TRIAL,'--db-filter=^'+TRIAL+'$','--db_user=dev_odoo18','--db_host='+str(socket),'--db_port=55443',
           '--addons-path='+str(base)+',/work/cerro-pg/source/addons','--data-dir='+str(work/'data'),
           '--logfile='+str(work/'data/followup-odoo.log'),'--no-http','--workers=0','--max-cron-threads=0','--without-demo=all',
           '--stop-after-init','--load=base,web']
    loader=['/usr/bin/python3.10',code/'load_cerro_catalog_contracts.py','--cerro-local-qa',*flags]
    audit=['/usr/bin/python3.10',code/'check_cerro_followup_catalogue.py',TRIAL]
    pre=ws/'qualified-192.json'
    if not pre.is_file():
        assert sql(TRIAL,"SELECT count(*) FROM ir_module_module WHERE state='installed'")=='192'
        call('odoo',loader+['-u','step_cerro_pack_reports,step_cerro_receipt_flow'],log='qualify-seed.log')
        physical=json.loads(call('postgres',audit+['--expected','192'],log='seed-catalogue.json'))
        pre.write_text(json.dumps(dict(receipt=digest(control),catalogue=physical),sort_keys=True))
    assert json.loads(pre.read_bytes())['receipt']==digest(control)
    with tempfile.TemporaryDirectory(dir=ws) as tmp:
        archive=Path(tmp)/'profile.tar'
        package_hash=build(HERE.parents[1],archive,'contact_followup')
        with tarfile.open(archive) as tar:
            for member in tar:
                p=Path(member.name)
                assert member.isfile() and p.parent==Path(MODULE) and p.suffix=='.py'
                dest=base/p
                dest.parent.mkdir(exist_ok=True)
                dest.write_bytes(tar.extractfile(member).read())
    if sql(TRIAL,"SELECT state FROM ir_module_module WHERE name='"+MODULE+"'")!='installed':
        call('odoo',loader+['-i',MODULE],log='first.log')
    assert sql(TRIAL,"SELECT state||'|'||latest_version FROM ir_module_module WHERE name='"+MODULE+"'")=='installed|18.0.1.0.0'
    physical=json.loads(call('postgres',audit,log='first-catalogue.json'))
    call('odoo',loader+['-u',MODULE],log='upgrade.log')
    assert json.loads(call('postgres',audit,log='upgrade-catalogue.json'))==physical
    shell=['/usr/bin/python3.10','/work/sys-fg-code/odoo-bin','shell',*flags]
    seq=['/usr/bin/python3.10',code/'check_cerro_pack_schema.py']
    before=json.loads(call('postgres',seq+['sequences']))
    head="import json,sys\nsys.path.insert(0,"+repr(str(code))+")\n"
    body=head+"""from probe_cerro_contact_followup import capture
from probe_cerro_followup_cases import descriptors,capture as cases,combinations,changes
from probe_cerro_followup_filters import capture as filters
from probe_cerro_followup_properties import exercise
from probe_cerro_reception_flow import containers
from probe_cerro_receipt_stock import capture as stock
r=capture(env)
print('real',json.dumps({k:v.get('sha256','denied') for k,v in r['contexts'].items()},sort_keys=True))
print('cases',json.dumps(dict(fields=descriptors(env),data=cases(env)),sort_keys=True))
print('mix',json.dumps(combinations(env),sort_keys=True))
print('changes',json.dumps(changes(env),sort_keys=True))
print('filters',json.dumps(filters(env),sort_keys=True))
print('properties',json.dumps(exercise(env),sort_keys=True))
print('receiving',json.dumps(containers(env),sort_keys=True))
print('stock',json.dumps(stock(env),sort_keys=True))
"""
    try:
        call('odoo',shell,body.encode(),'financial-user.log')
    finally:
        call('postgres',seq+['restore-sequences'],json.dumps(before).encode())
        assert json.loads(call('postgres',seq+['sequences']))==before
    raw=gzip.decompress((art/'native-followup-contact-u46.json.gz').read_bytes())
    assert hashlib.sha256(raw).hexdigest()=='3085ddbf2ce5e12e47a25d2f9f50bb3a9d3245330630bcce82e2df7626f8c711'
    expected=json.loads(raw)['contexts']
    log=ws/'financial-user.log'
    assert receipt(log,'real')=={k:v.get('sha256','denied') for k,v in expected.items()}
    for key,(name,checksum) in REFERENCES.items():
        path=art/name
        assert digest(path)==checksum and relative_dates(receipt(log,key))==relative_dates(json.loads(path.read_bytes())),key
    for key,name in [('receiving','native-fruit-receipt-container-u46.json'),('stock','native-receipt-stock-u46.json')]:
        assert receipt(log,key)==json.loads((art/name).read_bytes()),key
    common=head+"""from probe_cerro_studio_fullread import capture as full
from probe_cerro_studio_navigation import capture as routes
from probe_cerro_studio_client import capture as studio
print('VIEWS',json.dumps(dict(fullread=full(env),routes=routes(env),client=studio(env)),sort_keys=True))
env.cr.rollback()
"""
    call('odoo',shell,common.encode(),'followup-views.log')
    matrix=compare(receipt(art/'native-full.log','CERRO_FULL_READ'),receipt(art/'native-routes.log','CERRO_FULL'),
                   receipt(ws/'followup-views.log','VIEWS'))
    assert CONTACT in matrix['matching_full_record'] and len(matrix['matching_full_record'])>=22
    assert all(set(previous['matrix'][k])<=set(matrix[k]) for k in ('matching_full_record','matching_studio_values','original_routes'))
    assert physical==json.loads(call('postgres',audit,log='after-rollback-catalogue.json'))
    out=dict(seed=digest(control),archive=package_hash,objects=len(inventory),sequences=len(before),catalogue=physical,
             real_contexts=len(expected),real_rows=sum(v.get('records',0) for v in expected.values()),matrix=matrix,
             references={key:value[1] for key,value in REFERENCES.items()},properties=digest(art/'native-followup-properties-u46.json'))
    (ws/'accepted.json').write_text(json.dumps(out,sort_keys=True))
    print(digest(ws/'accepted.json'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--executor',type=Path,required=True)
    p.add_argument('--artifacts',type=Path,required=True)
    args=p.parse_args()
    with open('/dev/shm/steps-cerro-followup.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        run(args.executor,args.artifacts)
