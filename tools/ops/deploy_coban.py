"""Exact-package QA/deployment for the isolated Cerro Coban receiver. SSH/root only."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import tarfile
from datetime import datetime,timezone

BASE=Path('/opt/steps-validation/coban-receiver-20261031')
BACKEND=Path('/opt/fernando_odoo18/apis/backend/tracker_py')


def run(*args,**kw):return subprocess.run(args,check=True,**kw)


def cloud(*args):
    operator=os.environ.get('SUDO_USER');assert operator and operator!='root'
    return run('sudo','-u',operator,'gcloud',*args)


def query(database,sql):
    return subprocess.check_output(['sudo','-u','postgres','psql','-v','ON_ERROR_STOP=1','-At','-d',database],input=sql,text=True).strip()


def api_hash():
    digest=hashlib.sha256()
    for p in sorted((BACKEND/'app').rglob('*.py')):
        if '__pycache__' not in p.parts:
            digest.update(p.relative_to(BACKEND).as_posix().encode());digest.update(p.read_bytes().replace(b'\r\n',b'\n'))
    return digest.hexdigest()


def gps_snapshot():
    tables=query('tracker_steps',"SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'gps_%' ORDER BY tablename").splitlines()
    return {t:query('tracker_steps',"SELECT count(*)::text||':'||md5(COALESCE(string_agg(h,'' ORDER BY h),'')) FROM (SELECT md5(row_to_json(x)::text) h FROM "+t+" x) hashes") for t in tables}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['qa','deploy']);p.add_argument('archive',type=Path);p.add_argument('commit');p.add_argument('sha256');a=p.parse_args()
    assert os.geteuid()==0 and re.fullmatch('[a-f0-9]{40}',a.commit) and re.fullmatch('[a-f0-9]{64}',a.sha256)
    assert hashlib.sha256(a.archive.read_bytes()).hexdigest()==a.sha256
    BASE.mkdir(parents=True,exist_ok=True);BASE.chmod(0o755)
    stage=BASE/a.sha256[:16];stage.mkdir(exist_ok=True);stage.chmod(0o755)
    source=stage/'source';source.mkdir(exist_ok=True);source.chmod(0o755)
    with tarfile.open(a.archive) as archive:
        for member in archive.getmembers():
            path=Path(member.name)
            assert not path.is_absolute() and '..' not in path.parts and not member.issym() and not member.islnk()
            assert path.parts[0] in ('receivers','tools','docs')
        archive.extractall(source)
    with open('/run/lock/steps-environments.lock','a') as lease:
        print('COBAN_WAIT_SHARED_LEASE',flush=True);fcntl.flock(lease,fcntl.LOCK_EX)
        current_api=api_hash()
        if a.action=='qa':
            assert not (stage/'qa.json').exists(),'Use a fresh QA stage for a changed package'
            private=stage/'private';private.mkdir(exist_ok=True,mode=0o700);private.chmod(0o700)
            before=gps_snapshot();stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            database='COBAN_QA_'+stamp;dump=private/'tracker_steps.dump'
            with dump.open('wb') as output:run('sudo','-u','postgres','pg_dump','-Fc','tracker_steps',stdout=output)
            run('pg_restore','--file=/dev/null',str(dump))
            run('sudo','-u','postgres','createdb',database)
            try:
                with dump.open('rb') as inp:run('sudo','-u','postgres','pg_restore','--no-owner','--no-acl','-d',database,stdin=inp)
                with (private/'unit.log').open('w') as log:run('/usr/bin/python3.10','-m','unittest','receivers.coban.test_receiver','-v',cwd=source,stdout=log,stderr=subprocess.STDOUT)
                assert 'Ran 22 tests' in (private/'unit.log').read_text() and '\nOK' in (private/'unit.log').read_text()
                api_source=stage/'api-source';api_source.mkdir()
                shutil.copytree(BACKEND/'app',api_source/'app',ignore=shutil.ignore_patterns('__pycache__'))
                with (private/'flow.log').open('w') as log:
                    run('sudo','-u','postgres','env','DATABASE_URL=postgresql+psycopg2:///'+database,'JWT_SECRET=test-only-coban-rehearsal','PYTHONPATH='+str(source)+':'+str(api_source),str(BACKEND/'.venv/bin/python'),'-m','receivers.coban.rehearse',cwd=source,stdout=log,stderr=subprocess.STDOUT)
                assert 'COBAN_COPY_QA_OK' in (private/'flow.log').read_text()
                assert before==gps_snapshot() and current_api==api_hash(),'Production changed during QA; investigate and repeat from a fresh copy'
                (stage/'qa.json').write_text(json.dumps({'commit':a.commit,'sha256':a.sha256,'api_sha256':current_api,'database':database,'tests':22,'copy_flow':True,'production_untouched':True,'dump_sha256':hashlib.sha256(dump.read_bytes()).hexdigest()},indent=2))
                print('COBAN_QA_OK tests=22 tcp_to_copy_api=True production_untouched=True',flush=True)
            finally:run('sudo','-u','postgres','dropdb','--if-exists',database)
            return
        proof=json.loads((stage/'qa.json').read_text());assert proof['commit']==a.commit and proof['sha256']==a.sha256 and proof['api_sha256']==current_api and proof['copy_flow'] is True
        before=gps_snapshot();stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');backup=BASE/('backup-'+stamp);backup.mkdir(mode=0o700)
        for name,path in [('unit',Path('/etc/systemd/system/steps-coban.service')),('config',Path('/etc/steps-coban')),('data',Path('/var/lib/steps-coban'))]:
            if path.exists():shutil.copytree(path,backup/name) if path.is_dir() else shutil.copy2(path,backup/name)
        # Initial publication only. Existing receivers require a separately
        # reviewed upgrade; never replace a running installation by accident.
        assert not Path('/etc/systemd/system/steps-coban.service').exists(),'Receiver already installed; review upgrade explicitly'
        try:identity=pwd.getpwnam('steps-coban')
        except KeyError:
            run('useradd','--system','--home-dir','/var/lib/steps-coban','--shell','/usr/sbin/nologin','steps-coban');identity=pwd.getpwnam('steps-coban')
        release=Path('/opt/steps-coban/releases')/a.commit;release.mkdir(parents=True)
        shutil.copytree(source/'receivers',release/'receivers')
        for path in [release,*release.rglob('*')]:
            path.chmod(0o755 if path.is_dir() else 0o644)
        config=Path('/etc/steps-coban');config.mkdir(mode=0o750);os.chown(config,0,identity.pw_gid)
        data=Path('/var/lib/steps-coban');data.mkdir(mode=0o700);os.chown(data,identity.pw_uid,identity.pw_gid)
        credentials=json.loads(Path('/etc/tracker-bridge-keys.json').read_text());assert credentials.get('CERRO_EL_PLOMO')
        values={'bridge-key.json':{'issuer':'CERRO_EL_PLOMO','key':credentials['CERRO_EL_PLOMO']},'devices.json':{},'config.json':{'host':'0.0.0.0','port':5001,'api':'http://127.0.0.1:8000','key_file':'/etc/steps-coban/bridge-key.json','mapping':'/etc/steps-coban/devices.json','database':'/var/lib/steps-coban/inbox.sqlite'}}
        for name,value in values.items():
            path=config/name;path.write_text(json.dumps(value,indent=2));path.chmod(0o640);os.chown(path,0,identity.pw_gid)
        current=Path('/opt/steps-coban/current');assert not current.exists();current.symlink_to(release,target_is_directory=True)
        unit=Path('/etc/systemd/system/steps-coban.service');shutil.copy2(source/'receivers/coban/steps-coban.service',unit)
        firewall_created=False
        try:
            run('systemctl','daemon-reload');run('systemctl','enable','--now','steps-coban.service')
            run('systemctl','is-active','--quiet','steps-coban.service')
            cloud('compute','instances','add-tags','odoo-new','--zone=us-central1-c','--project=stepsconsulting','--tags=steps-coban-cerro','--quiet')
            cloud('compute','firewall-rules','create','steps-coban-cerro-tcp5001','--project=stepsconsulting','--network=red-vpc-steps','--direction=INGRESS','--allow=tcp:5001','--source-ranges=0.0.0.0/0','--target-tags=steps-coban-cerro','--description=Coban GPS103 TCP receiver - Cerro commissioning allowlist','--quiet')
            firewall_created=True
            assert before==gps_snapshot() and proof['api_sha256']==api_hash(),'Unrelated production source/data change detected'
            (stage/'deployment.json').write_text(json.dumps({'commit':a.commit,'sha256':a.sha256,'backup':str(backup),'port':5001,'protocol':'gps103-ascii','allowlist_count':0,'api_untouched':True,'production_data_untouched':True},indent=2))
            print('COBAN_DEPLOY_OK port=5001 allowlist=0 backup='+str(backup),flush=True)
        except Exception:
            run('systemctl','disable','--now','steps-coban.service')
            operator=os.environ.get('SUDO_USER')
            if firewall_created:subprocess.run(['sudo','-u',operator,'gcloud','compute','firewall-rules','delete','steps-coban-cerro-tcp5001','--project=stepsconsulting','--quiet'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            raise


if __name__=='__main__':main()
