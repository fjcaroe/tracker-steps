"""Copy-certified, additive Tracker analytics API publication. No Odoo upgrade.

Preserves receiver, mobile, secrets, all unpatched API files and business rows.
Frontend is published separately with deploy_tracker_frontend.py after API QA.
"""
import argparse,fcntl,hashlib,json,os,shutil,subprocess,time
from pathlib import Path
from datetime import datetime,timezone
from urllib.request import urlopen
from deploy_gps_commissioning import tree,columns,snapshot,query,run

BASE=Path('/opt/steps-validation/tracker-analytics')
API=Path('/opt/fernando_odoo18/apis/backend/tracker_py')
VENV=API/'.venv/bin/python'
FILES=('main.py','routers/fleet.py','routers/gps_analytics.py','services/gps_metrics.py','services/gps_analytics.py')
TARGETS={'development':(Path('/opt/steps-tracker-development/current/backend/tracker_py'),'steps-tracker-dev-api','tracker_steps_development',8012),
         'production':(API,'tracker-steps-api','tracker_steps',8000)}


def ready(port):
    for _ in range(40):
        try:
            with urlopen(f'http://127.0.0.1:{port}/openapi.json',timeout=3) as r:
                paths=json.load(r)['paths']
            assert '/v1/assets/analytics' in paths and '/v1/ingest/positions' in paths and '/mobile/services' in paths
            return
        except (OSError,AssertionError):time.sleep(1)
    raise RuntimeError('Analytics API readiness failed')


def prepare(source,target,stage):
    root=stage/target;root.mkdir(parents=True,exist_ok=False)
    live=TARGETS[target][0]
    shutil.copytree(live/'app',root/'app',ignore=shutil.ignore_patterns('__pycache__'))
    before=tree(live/'app')
    for name in FILES:
        dest=root/'app'/name;dest.parent.mkdir(exist_ok=True,parents=True)
        shutil.copy2(source/'backend/tracker_py/app'/name,dest)
    shutil.copy2(source/'backend/tracker_py/scripts/refresh_gps_analytics.py',root/'refresh_gps_analytics.py')
    for path in [root,*root.rglob('*')]:path.chmod(0o755 if path.is_dir() else 0o644)
    after=tree(root/'app')
    assert {k:v for k,v in before.items() if k not in FILES}=={k:v for k,v in after.items() if k not in FILES}
    return root,before,after


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['qa','development','production']);p.add_argument('source',type=Path);a=p.parse_args()
    assert os.geteuid()==0;source=a.source.resolve()
    commit=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
    assert not subprocess.check_output(['git','-C',str(source),'status','--porcelain','--untracked-files=no'],text=True).strip()
    stage=BASE/commit;stage.mkdir(parents=True,exist_ok=True);stage.chmod(0o755)
    private=stage/'private';private.mkdir(exist_ok=True,mode=0o700)
    migration=source/'backend/tracker_py/migrations/20261106_gps_analytics.up.sql'
    with open('/run/lock/steps-environments.lock','a') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX)
        if a.action=='qa':
            proof={'commit':commit,'migration':hashlib.sha256(migration.read_bytes()).hexdigest(),'targets':{}}
            assert not (stage/'qa.json').exists()
            for target,(live,service,database,port) in TARGETS.items():
                root,before,after=prepare(source,target,stage)
                db='TRACKER_ANALYTICS_QA_'+target+'_'+commit[:10]
                dump=private/(target+'.dump')
                with dump.open('wb') as out:run('sudo','-u','postgres','pg_dump','-Fc',database,stdout=out)
                run('sudo','-u','postgres','createdb',db)
                try:
                    with dump.open('rb') as inp:run('sudo','-u','postgres','pg_restore','--no-owner','--no-acl','-d',db,stdin=inp)
                    cols=columns(db);original=snapshot(db,cols)
                    run('sudo','-u','postgres','psql','-v','ON_ERROR_STOP=1','-d',db,'-f',migration,stdout=subprocess.DEVNULL)
                    assert snapshot(db,cols)==original,'Migration changed existing business data'
                    env=['env','DATABASE_URL=postgresql+psycopg2:///'+db,'JWT_SECRET=private-copy-test-only','PYTHONPATH='+str(root)+':/opt/steps-validation/personal-transfer-test-deps']
                    with (private/(target+'-tests.log')).open('w') as out:
                        run('sudo','-u','postgres',*env,VENV,'-m','pytest',source/'backend/tracker_py/tests/test_gps_metrics.py',source/'backend/tracker_py/tests/test_fleet.py',source/'backend/tracker_py/tests/test_receiver.py','-q',cwd=root,stdout=out,stderr=subprocess.STDOUT)
                        run('sudo','-u','postgres',*env,VENV,source/'tools/qa/tracker/analytics-copy.py',cwd=root,stdout=out,stderr=subprocess.STDOUT)
                    assert snapshot(db,cols)==original,'QA changed original business rows'
                    proof['targets'][target]={'before':before,'after':after,'business_rows_preserved':True,'tests':str(private/(target+'-tests.log'))}
                    print('TRACKER_ANALYTICS_QA_OK '+target,flush=True)
                finally:run('sudo','-u','postgres','dropdb','--if-exists',db)
            (stage/'qa.json').write_text(json.dumps(proof,indent=2));return
        proof=json.loads((stage/'qa.json').read_text());assert proof['commit']==commit
        if a.action=='production':assert (stage/'development.json').is_file()
        target=a.action;live,service,database,port=TARGETS[target];root=stage/target
        assert tree(live/'app')==proof['targets'][target]['before'],'Concurrent API change; repeat copy QA'
        assert tree(root/'app')==proof['targets'][target]['after']
        assert hashlib.sha256(migration.read_bytes()).hexdigest()==proof['migration']
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');backup=private/(target+'-backup-'+stamp);backup.mkdir(mode=0o700)
        with (backup/'database.dump').open('wb') as out:run('sudo','-u','postgres','pg_dump','-Fc',database,stdout=out)
        shutil.copytree(live/'app',backup/'app',ignore=shutil.ignore_patterns('__pycache__'))
        release=Path('/opt/steps-tracker-analytics/releases')/target/commit
        assert not release.exists();release.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(root,release)
        if (live/'.env').exists():(release/'.env').symlink_to(live/'.env')
        for path in [release,*release.rglob('*')]:
            if not path.is_symlink():path.chmod(0o755 if path.is_dir() else 0o644)
        run('sudo','-u','postgres','psql','-v','ON_ERROR_STOP=1','-d',database,'-f',migration,stdout=subprocess.DEVNULL)
        dropdir=Path('/etc/systemd/system')/(service+'.service.d');dropdir.mkdir(exist_ok=True)
        override=dropdir/'70-analytics.conf'
        assert not override.exists(),'Review existing analytics override before upgrading'
        override.write_text('[Service]\nWorkingDirectory='+str(release)+'\n')
        user=subprocess.check_output(['systemctl','show',service,'-p','User','--value'],text=True).strip();assert user
        worker='steps-tracker-analytics-'+target
        envline='EnvironmentFile=/etc/steps-tracker-development.env\n' if target=='development' else ''
        Path('/etc/systemd/system/'+worker+'.service').write_text('[Unit]\nDescription=Steps GPS analytics rollups '+target+'\nAfter=postgresql.service\n[Service]\nType=oneshot\nUser='+user+'\nWorkingDirectory='+str(release)+'\n'+envline+'Environment=PYTHONDONTWRITEBYTECODE=1\nExecStart='+str(VENV)+' '+str(release/'refresh_gps_analytics.py')+' --limit 500\nNoNewPrivileges=true\nPrivateTmp=true\nTimeoutStartSec=120\n')
        Path('/etc/systemd/system/'+worker+'.timer').write_text('[Unit]\nDescription=Refresh Steps GPS analytics '+target+'\n[Timer]\nOnBootSec=30s\nOnUnitInactiveSec=30s\nAccuracySec=5s\n[Install]\nWantedBy=timers.target\n')
        try:
            run('systemctl','daemon-reload');run('systemctl','restart',service);ready(port)
            run('systemctl','enable','--now',worker+'.timer');run('systemctl','start',worker+'.service')
        except Exception:
            override.unlink(missing_ok=True);run('systemctl','daemon-reload');run('systemctl','restart',service)
            raise
        assert tree(release/'app')==proof['targets'][target]['after']
        # Pin all historical buckets before publishing the summary-dependent UI.
        for _ in range(200):
            pending=int(query(database,"SELECT count(*) FROM gps_analytics_dirty WHERE bucket<date_trunc('hour',now())-interval '1 hour' AND bucket>=now()-interval '32 days'"))
            if pending==0:break
            run('systemctl','start',worker+'.service')
        assert pending==0,'Backfill incomplete; keep previous frontend'
        result={'commit':commit,'source':str(release),'backup':str(backup),'api':proof['targets'][target]['after'],'database':database,'rollups_ready':True}
        (stage/(target+'.json')).write_text(json.dumps(result,indent=2))
        print('TRACKER_ANALYTICS_PUBLISHED '+target,flush=True)


if __name__=='__main__':main()
