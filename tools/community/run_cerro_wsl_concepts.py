"""Run the native payment-concept comparison and the full Cerro view regression on the private local PG12 restore."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from prepare_cerro_wsl_pilots import ROOT,WORK,INSIDE
from compare_cerro_studio_receipts import receipt,compare

DB='COMMUNITY_CERRO_BOM_CONCEPTS_20261127U45P'
SOURCE='COMMUNITY_CERRO_BOM_CONTRACTS_20261127U44M'
MODULE='step_cerro_export_payment_concepts'
ALIAS='odoo_studio_step_exp_190b5787-3bb7-4f94-b7cb-b1b9a20d75cd'
POST=WORK/'concepts'
UID=61018


def run(executor,artifacts):
    assert os.getuid()==0 and (ROOT/'pg-source-members.json').is_file()
    assert shutil.disk_usage('/mnt/c').free > 2*1024**3
    sealed=WORK/('restore-'+SOURCE)
    restore=json.loads((sealed/'recovered.json').read_bytes())
    assert restore['rows']==249641 and restore['tables']==1521 and restore['objects']==677
    assert hashlib.sha256((artifacts/'original-required.json').read_bytes()).hexdigest()=='600e83a8eb07c6ed54c13f86c10347f759f9592139ee2a78a978629698f08367'
    assert hashlib.sha256((artifacts.parent/'cerro-u45p-native-concept-user.json').read_bytes()).hexdigest()=='49fa2ff286f841f0bd25a38700befa33b4f963c83af0b52b32ed0b246fdfa9fc'
    POST.mkdir(exist_ok=True,mode=0o751)
    for name in ('load_cerro_catalog_contracts.py','check_cerro_local_catalogue.py','probe_cerro_payment_concepts.py',
                 'probe_cerro_studio_fullread.py','probe_cerro_studio_views.py','probe_cerro_studio_client.py',
                 'probe_cerro_studio_navigation.py','audit_cerro_original_schema.py'):
        f=WORK/'code'/name
        shutil.copyfile(Path(__file__).with_name(name),f)
        f.chmod(0o644)
    plan=json.loads((artifacts/'original-required.json').read_bytes())
    assert len(plan['fields'])==29 and plan['database']==SOURCE
    plan['database']=DB
    (POST/'original-required.json').write_text(json.dumps(plan,sort_keys=True))
    def execute(user,args,input_data=None,log=None):
        process=subprocess.run(['python3',str(executor),'--user',user,'--',*map(str,args)],input=input_data,
                               stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        if log:
            log.write_bytes(process.stdout)
        if process.returncode!=0:
            raise RuntimeError((process.stdout.decode(errors='replace')[-900:]) or 'See the private Odoo runtime log')
        return process.stdout.decode()
    db_args=['-h',INSIDE/'socket','-p','55442']
    def query(db,sql):
        return execute('postgres',['psql','-XAt','-v','ON_ERROR_STOP=1',*db_args,'-d',db,'-c',sql]).strip()
    marker=POST/'clone-source.json'
    owner=query('postgres',"SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='"+DB+"'")
    if not marker.exists():
        assert not owner
        marker.write_text(json.dumps(dict(source=SOURCE,archive=restore['archive'],trial=DB),sort_keys=True))
    assert json.loads(marker.read_bytes())['archive']==restore['archive']
    if not owner:
        execute('postgres',['createdb',*db_args,'--owner=dev_odoo18','--template='+SOURCE,DB])
    else:
        assert owner=='dev_odoo18'
    data=POST/'data'
    destination=data/'filestore'/DB
    destination.mkdir(parents=True,exist_ok=True)
    for dirname in [data,data/'filestore',destination]:
        os.chown(dirname,UID,UID)
        dirname.chmod(0o700)
    manifest=json.loads((artifacts/(SOURCE+'-inventory')).read_bytes())['objects']
    for name,(sha,size) in manifest.items():
        src=sealed/'data/filestore'/SOURCE/name
        dst=destination/name
        dst.parent.mkdir(exist_ok=True)
        os.chown(dst.parent,UID,UID)
        if not dst.exists():
            shutil.copyfile(src,dst)
        assert src.stat().st_ino!=dst.stat().st_ino and dst.stat().st_size==size and hashlib.sha1(dst.read_bytes()).hexdigest()==sha
        os.chown(dst,UID,UID)
        dst.chmod(0o600)
    inner='/work/cerro-pg'
    opts=['-d',DB,'--db-filter=^'+DB+'$','--db_user=dev_odoo18','--db_host='+inner+'/socket','--db_port=55442',
          '--addons-path='+inner+'/source/addons','--data-dir='+inner+'/concepts/data','--logfile='+inner+'/concepts/data/odoo.log',
          '--load=base,web','--no-http','--workers=0','--max-cron-threads=0','--stop-after-init','--without-demo=all']
    for flag,phase in [('-i','install'),('-u','upgrade')]:
        execute('odoo',['/usr/bin/python3.10',inner+'/code/load_cerro_catalog_contracts.py','--cerro-local-qa',*opts,flag,MODULE],
                log=POST/(phase+'.log'))
        assert query(DB,"SELECT state||'|'||latest_version FROM ir_module_module WHERE name='"+MODULE+"'")=='installed|18.0.1.0.1'
        check=execute('postgres',['/usr/bin/python3.10',inner+'/code/check_cerro_local_catalogue.py'],log=POST/(phase+'-schema.json'))
        assert json.loads(check)['census']==[189,0,0]
    shell=['/usr/bin/python3.10','/work/sys-fg-code/odoo-bin','shell',*opts]
    body="""import sys,json
sys.path.insert(0,'/work/cerro-pg/code')
from probe_cerro_payment_concepts import exercise
print('PAYMENT_USER',json.dumps(exercise(env),sort_keys=True))
"""
    seq=['/usr/bin/python3.10',inner+'/code/check_cerro_local_catalogue.py']
    before=json.loads(execute('postgres',[*seq,'sequences']))
    try:
        execute('odoo',shell,body.encode(),POST/'payment-user.log')
    finally:
        restored=json.loads(execute('postgres',[*seq,'restore-sequences'],json.dumps(before).encode()))
        assert json.loads(execute('postgres',[*seq,'sequences']))==before
    user=receipt(POST/'payment-user.log','PAYMENT_USER')
    original=json.loads((artifacts.parent/'cerro-u45p-native-concept-user.json').read_bytes())
    assert user==original['user'] and restored==original['sequences_restored']
    views="""import sys,json
sys.path.insert(0,'/work/cerro-pg/code')
from probe_cerro_studio_fullread import capture as fullread
from probe_cerro_studio_navigation import capture as routes
from probe_cerro_studio_client import capture as client
print('CERRO_CONCEPT_VIEWS',json.dumps(dict(fullread=fullread(env),routes=routes(env),client=client(env)),sort_keys=True))
env.cr.rollback()
"""
    execute('odoo',shell,views.encode(),POST/'concept-views.log')
    actual=receipt(POST/'concept-views.log','CERRO_CONCEPT_VIEWS')
    matrix=compare(receipt(artifacts/'native-full.log','CERRO_FULL_READ'),receipt(artifacts/'native-routes.log','CERRO_FULL'),actual)
    before_matrix=json.loads((artifacts.parent/'cerro-u44m-accepted-views.json').read_bytes())['matrix']
    for key in ('matching_full_record','matching_studio_values','original_routes'):
        assert set(before_matrix[key])<=set(matrix[key])
    assert ALIAS in matrix['matching_full_record'] and ALIAS in matrix['matching_studio_values'] and '4845' in matrix['original_routes']
    assert any(route['action']==1378 and 987 in route['menus'] for route in actual['routes']['direct_menu_routes']['4845'])
    result=dict(user=user,matrix=matrix,schema=json.loads(execute('postgres',seq)),native_user_sha256=hashlib.sha256(
                (artifacts.parent/'cerro-u45p-native-concept-user.json').read_bytes()).hexdigest(),
                source_archive_sha256=restore['archive'],restored_sequences=restored,objects=len(manifest),view=4845,action=1378,menu=987)
    (POST/'accepted-concepts.json').write_text(json.dumps(result,sort_keys=True))
    print(hashlib.sha256((POST/'accepted-concepts.json').read_bytes()).hexdigest())


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--executor',type=Path,required=True)
    cli.add_argument('--artifacts',type=Path,required=True)
    args=cli.parse_args()
    run(args.executor,args.artifacts)
