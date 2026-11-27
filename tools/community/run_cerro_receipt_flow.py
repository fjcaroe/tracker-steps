"""Rebuild Cerro 189 to 192 in a single private PG12 replica and exercise its original inbound stock operation."""
import argparse
import fcntl
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
from prepare_cerro_wsl_packing_cold import RAM, SOURCE, prepare
from prepare_cerro_wsl_pilots import WORK

HERE=Path(__file__).parent
TRIAL='COMMUNITY_CERRO_BOM_PACKING_20261127U46D'
REFERENCE={
    'profiles':['probe_cerro_receipt_import_access','model_access','native-fruit-model-access-u46.json',
                '21a571ee5e41a3b4c0ef56dae8a87e322ec06837eaaadbb03651e5666b9458e9'],
    'fruit':['probe_cerro_reception_flow','containers','native-fruit-receipt-container-u46.json',
             'c455217d3098ed9daba73fa16bc0f1f8d4de602ab7db70ec3177124186a8324b'],
    'import':['probe_cerro_receipt_import_access','exercise','native-fruit-import-access-u46.json',
              '7cb775f078a2fbf832f3adacf4b88bc7a82b82d845fc63ada0ca9793d0ce6a44'],
    'stock':['probe_cerro_receipt_stock','capture','native-receipt-stock-u46.json',
             '4c418eba0f20faff2aea1b4cbafd3ac80a2d02ee204d0af4a36bfd14f53b35fe'],
    'orders':['probe_cerro_pack_report_rows','capture','native-pack-orders-u46.json',None],
    'performance':['probe_cerro_pack_report_rows','controls','native-pack-report-controls-u46.json',None],
    'quality':['probe_cerro_picking_lists','exercise','native-picking-search-u46.json',None],
    'quality_search':['probe_cerro_picking_lists','search_cases','native-picking-mixed-search-u46.json',None],
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stage(profile, dest):
    with tempfile.TemporaryDirectory(dir=dest.parent) as temp:
        archive=Path(temp)/'admitted.tar'
        checksum=build(HERE.parents[1],archive,profile)
        with tarfile.open(archive) as bundle:
            for member in bundle:
                name=Path(member.name)
                if not member.isfile() or name.is_absolute() or '..' in name.parts or name.parts[0] not in (
                        'step_cerro_pack_reports','step_cerro_picking_list_history','step_cerro_receipt_flow'):
                    raise ValueError('Unexpected file in the receipt profile')
                path=dest/name
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(bundle.extractfile(member).read())
    return checksum


def run(executor,art):
    with open('/dev/shm/steps-shared-qa-restore.lock','a') as restore:
        fcntl.flock(restore,fcntl.LOCK_EX)
        seed=prepare(executor,TRIAL)
    ws=RAM/'packing-receipt'
    ws.mkdir(exist_ok=True)
    data=ws/'data'
    files=data/'filestore'/TRIAL
    files.mkdir(parents=True,exist_ok=True)
    for path in [data,data/'filestore',files]:
        os.chown(path,61018,61018)
        path.chmod(0o700)
    original=WORK/'concepts'
    census=json.loads((art/'COMMUNITY_CERRO_BOM_CONTRACTS_20261127U44M-inventory').read_bytes())['objects']
    assert len(census)==677
    for name,(checksum,size) in census.items():
        src=original/'data/filestore'/SOURCE/name
        target=files/name
        target.parent.mkdir(exist_ok=True)
        os.chown(target.parent,61018,61018)
        if not target.exists():
            shutil.copyfile(src,target)
        assert target.stat().st_size==size and target.stat().st_ino!=src.stat().st_ino
        assert hashlib.sha1(target.read_bytes()).hexdigest()==checksum
        os.chown(target,61018,61018)
        target.chmod(0o600)
    plan=json.loads((original/'original-required.json').read_bytes())
    assert plan['database']==SOURCE and len(plan['fields'])==29
    plan['database']=TRIAL
    (ws/'original-required.json').write_text(json.dumps(plan,sort_keys=True))
    code=ws/'code'
    code.mkdir(exist_ok=True)
    utilities=('load_cerro_catalog_contracts','check_cerro_receipt_catalogue','check_cerro_pack_schema','check_cerro_local_catalogue',
               'audit_cerro_original_schema','probe_cerro_studio_fullread','probe_cerro_studio_navigation','probe_cerro_studio_client',
               'probe_cerro_studio_views','probe_cerro_packing_landscape','probe_cerro_receipt_scope')
    for name in {*utilities,*(entry[0] for entry in REFERENCE.values())}:
        shutil.copyfile(HERE/(name+'.py'),code/(name+'.py'))
    flags=['-d',TRIAL,'--db-filter=^'+TRIAL+'$','--db_user=dev_odoo18','--db_host='+str(RAM/'socket'),'--db_port=55443',
           '--data-dir='+str(data),'--logfile='+str(data/'receipt-odoo.log'),'--no-http','--workers=0','--max-cron-threads=0',
           '--stop-after-init','--without-demo=all','--load=base,web']
    def command(user,args,body=None,log=None):
        result=subprocess.run(['python3',str(executor),'--user',user,'--',*map(str,args)],input=body,capture_output=True)
        if log:
            (ws/log).write_bytes(result.stdout+result.stderr)
        if result.returncode:
            raise ValueError((result.stdout+result.stderr).decode(errors='replace')[-1500:])
        return result.stdout.decode()
    def sql(query):
        return command('postgres',['psql','-h',str(RAM/'socket'),'-p','55443','-d',TRIAL,'-XAt','-v','ON_ERROR_STOP=1','-c',query]).strip()
    def version(module):
        return sql("SELECT state||'|'||COALESCE(latest_version,'') FROM ir_module_module WHERE name='"+module+"'")
    def upgrade(operation,module,flags,stage_name):
        command('odoo',['/usr/bin/python3.10',code/'load_cerro_catalog_contracts.py','--cerro-local-qa',*flags,operation,module],log=stage_name+'.log')
    def audit(number,stage_name):
        return json.loads(command('postgres',['/usr/bin/python3.10',code/'check_cerro_receipt_catalogue.py',str(number),'--trial',TRIAL],
                                  log=stage_name+'-catalogue.json'))
    base=ws/'addons'
    base.mkdir(exist_ok=True)
    flags.insert(0,'--addons-path='+str(base)+',/work/cerro-pg/source/addons')
    earlier=ws/'admitted-191.json'
    profiles={}
    for profile,module in [('picking','step_cerro_picking_list_history'),('pack_reports','step_cerro_pack_reports')]:
        profiles[profile]=stage(profile,base)
        if not version(module).startswith('installed|'):
            upgrade('-i',module,flags,'install-'+profile)
            assert version(module)=='installed|18.0.1.0.0'
    if not earlier.exists():
        earlier.write_text(json.dumps(dict(archives=profiles,seed=seed['sha256'],catalogue=audit(191,'191')),sort_keys=True))
    claim=json.loads(earlier.read_bytes())
    assert claim['archives']==profiles and claim['seed']==seed['sha256'] and claim['catalogue']['census']==191
    new=ws/'receipt-addons'
    profiles['receipt_flow']=stage('receipt_flow',new)
    flags[0]='--addons-path='+str(new)+','+str(base)+',/work/cerro-pg/source/addons'
    report='step_cerro_pack_reports'
    module='step_cerro_receipt_flow'
    if version(report)=='installed|18.0.1.0.0':
        upgrade('-u',report,flags,'prepare-receipt-stock')
    assert version(report)=='installed|18.0.1.0.1'
    if not version(module).startswith('installed|'):
        upgrade('-i',module,flags,'first-receipt')
    assert version(module)=='installed|18.0.1.0.0'
    installed=audit(192,'first-receipt')
    upgrade('-u',module,flags,'repeat-receipt')
    assert audit(192,'repeat-receipt')==installed
    seq=['/usr/bin/python3.10',code/'check_cerro_pack_schema.py','--receipt-d']
    before=json.loads(command('postgres',seq+['sequences']))
    head="import sys,json\nsys.path.insert(0,"+repr(str(code))+")\n"
    body=head
    for marker,(source,method,_,_) in REFERENCE.items():
        body+="from "+source+" import "+method+" as probe\nprint("+repr(marker)+",json.dumps(probe(env),sort_keys=True))\n"
    body+="from probe_cerro_receipt_scope import exercise\nprint('scope',json.dumps(exercise(env),sort_keys=True))\n"
    shell=['/usr/bin/python3.10','/work/sys-fg-code/odoo-bin','shell',*flags]
    try:
        command('odoo',shell,body.encode(),'receipt-user.log')
    finally:
        command('postgres',seq+['restore-sequences'],json.dumps(before).encode())
        assert json.loads(command('postgres',seq+['sequences']))==before
    matched={}
    for name,(_,_,file,signature) in REFERENCE.items():
        path=art/file
        assert receipt(ws/'receipt-user.log',name)==json.loads(path.read_bytes()), name
        matched[name]=digest(path)
        if signature:
            assert matched[name]==signature
    body=head+"""from probe_cerro_studio_fullread import capture as full
from probe_cerro_studio_navigation import capture as routes
from probe_cerro_studio_client import capture as studio
from probe_cerro_packing_landscape import capture as landscape
print('VIEWS',json.dumps(dict(fullread=full(env),routes=routes(env),client=studio(env)),sort_keys=True))
print('FORM',json.dumps(landscape(env)['5245'],sort_keys=True))
env.cr.rollback()
"""
    command('odoo',shell,body.encode(),'receipt-views.log')
    views=receipt(ws/'receipt-views.log','VIEWS')
    matrix=compare(receipt(art/'native-full.log','CERRO_FULL_READ'),receipt(art/'native-routes.log','CERRO_FULL'),views)
    native=json.loads((art/'native-packing-fields-u46.json').read_bytes())['5245']
    candidate=receipt(ws/'receipt-views.log','FORM')
    absent=[key for key in native['fields'] if key not in candidate['fields'] or candidate['fields'][key].get('absent')]
    actions=[key for key in native['buttons'] if not candidate['buttons'].get(key)]
    previous=json.loads((art/'u46c-accepted.json').read_bytes())['matrix']
    assert all(set(previous[k])<=set(matrix[k]) for k in ('original_routes','matching_full_record','matching_studio_values'))
    assert len(absent)<=23 and len(actions)<=15 and len(matrix['original_routes'])==len(matrix['matching_studio_values'])==23
    assert installed==audit(192,'after-rollback')
    result=dict(archives=profiles,seed=seed['sha256'],files=len(census),catalogue=installed,matching=matched,
                scope=receipt(ws/'receipt-user.log','scope'),matrix=matrix,absent=absent,actions=actions,sequences=len(before))
    (ws/'accepted-receipt.json').write_text(json.dumps(result,sort_keys=True))
    print(digest(ws/'accepted-receipt.json'))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executor',required=True,type=Path)
    parser.add_argument('--artifacts',required=True,type=Path)
    args=parser.parse_args()
    with open('/dev/shm/steps-cerro-receipt.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        run(args.executor,args.artifacts)
