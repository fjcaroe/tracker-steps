"""Compare the real OCA API adapter with a fresh Cerro Enterprise reference.

The reference does not install OCA or convert Cerro. No active environment deploy.
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
import socket
import subprocess
import sys

MODULES=('step_payroll_contracts','step_payroll_oca_api','step_payroll_enterprise_reference')
OFFICIAL_PIN='4b4efe68291d6def5bb7d2e1f2b829e0cda577d4'
PIN='4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e'


def run(*args,**kw):return subprocess.run(args,check=True,**kw)


def main():
    global MODULES
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('community','cerro-reference'))
    parser.add_argument('--profile',choices=('api','simpledigital'),default='api')
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--database',required=True)
    parser.add_argument('--runtime',type=Path,required=True)
    parser.add_argument('--oca',type=Path,required=True)
    args=parser.parse_args()
    if args.profile=='simpledigital':
        MODULES=MODULES+('step_simpledigital_oca_base','step_simpledigital_oca_security','l10n_cl_simpledigital_payroll')
    assert os.geteuid()==0 and str(args.root.resolve()).startswith('/opt/steps-validation/')
    assert re.fullmatch(('COMMUNITY_PAYROLL_API_' if args.mode=='community' else 'MANAGEMENT_QA_CERRO_PAYROLL_API_')+'[A-Za-z0-9_]+',args.database)
    root=args.root.resolve();source=root/'addons';stage=root/args.mode
    assert not stage.exists();stage.mkdir(mode=0o750)
    fp={str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for m in MODULES
        for p in sorted((source/m).rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
    assert all((source/m/'__manifest__.py').exists() for m in MODULES)
    (stage/'source-files.json').write_text(json.dumps(fp,indent=2))
    pure=args.mode=='community';conf=Path('/etc/dev_odoo18.conf' if pure else '/etc/odoo18-cerroelplomo.conf')
    config=configparser.ConfigParser(interpolation=None);assert config.read(conf)
    user='odoo' if pure else 'cerro_odoo18';identity=pwd.getpwnam(user)
    data=stage/'data';data.mkdir();overlay=stage/'addons';overlay.mkdir()
    for m in (tuple(m for m in MODULES if m!='step_payroll_enterprise_reference') if pure else (MODULES[0],MODULES[2])):(overlay/m).symlink_to(source/m)
    sys.path.insert(0,str(source/'tools/community'))
    import validate_agriculture_core as preservation
    preservation.MODULES=preservation.BASE_MODULES+preservation.PRODUCER_MODULES+preservation.OPERATIONS_MODULES+preservation.LABOR_MODULES+preservation.HARVEST_MODULES+preservation.HR_MODULES
    from validate_community_reports import sql,same_values
    from manage_community_reports import runtime_contract
    def dump_json(name,value):(stage/(name+'.json')).write_text(json.dumps(value,indent=2))
    if pure:
        for path,url in ((args.runtime,'https://github.com/odoo/odoo.git'),(args.oca,'https://github.com/OCA/payroll.git')):
            assert run('git','-C',str(path),'remote','get-url','origin',capture_output=True,text=True).stdout.strip()==url
            assert not run('git','-C',str(path),'status','--porcelain',capture_output=True,text=True).stdout.strip()
        assert run('git','-C',str(args.runtime),'rev-parse','HEAD',capture_output=True,text=True).stdout.strip()==OFFICIAL_PIN
        assert run('git','-C',str(args.oca),'rev-parse','HEAD',capture_output=True,text=True).stdout.strip()==PIN
        for m in ('payroll','payroll_account'):(overlay/m).symlink_to(args.oca/m)
        dump_json('vendor-files',{str(p.relative_to(args.oca)):hashlib.sha256(p.read_bytes()).hexdigest()
            for m in ('payroll','payroll_account') for p in sorted((args.oca/m).rglob('*')) if p.is_file() and '__pycache__' not in p.parts})
    with open('/run/lock/steps-environments.lock','a') as lock:
        print('PAYROLL_API_WAITING_FOR_SHARED_LEASE '+args.mode,flush=True);fcntl.flock(lock,fcntl.LOCK_EX)
        assert not sql('postgres',"SELECT 1 FROM pg_database WHERE datname='"+args.database+"'")
        run('sudo','-u','postgres','createdb','--owner='+config['options']['db_user'],args.database)
        baseline=original=history=contract=None
        if not pure:
            assert config['options']['db_name']=='CERRO_EL_PLOMO'
            with (stage/'source.dump').open('wb') as out:run('sudo','-u','postgres','pg_dump','-Fc','CERRO_EL_PLOMO',stdout=out)
            with (stage/'source.dump').open('rb') as inp:run('sudo','-u','postgres','pg_restore','--no-owner','--no-acl','--no-comments','--role='+config['options']['db_user'],'-d',args.database,stdin=inp)
            sql(args.database,'UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false;')
            store=data/'filestore'/args.database;store.mkdir(parents=True)
            run('rsync','-a',str(Path(config['options']['data_dir'])/'filestore/CERRO_EL_PLOMO')+'/',str(store)+'/')
            contract=runtime_contract(conf);dump_json('source-contract',contract)
            baseline=preservation.snapshot(args.database);original=preservation.identity_contract(args.database);history=preservation.history_contract(args.database)
            for name,value in [('business-before',baseline),('identity-before',original),('history-before',history)]:dump_json(name,value)
        for p in [stage,*stage.rglob('*')]:
            if not p.is_symlink():os.chown(p,identity.pw_uid,identity.pw_gid)
        with socket.socket() as listener:listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
        paths=str(overlay)+','+(str(args.runtime/'addons') if pure else config['options']['addons_path'])
        entry=args.runtime/'odoo-bin' if pure else source/'tools/ops/run_agriculture_upgrade.py'
        base=['sudo','-u',user,'/usr/bin/python3.10',str(entry)]
        opts=['-c',str(conf),'-d',args.database,'--db-filter=^'+args.database+'$','--addons-path='+paths,
            '--data-dir='+str(data),'--load=base,web','--workers=0','--max-cron-threads=0',
            '--http-interface=127.0.0.1','--http-port='+str(port),'--gevent-port=0','--without-demo='+('' if pure else 'all')]
        modules=('step_simpledigital_oca_security' if args.profile=='simpledigital' else 'step_payroll_oca_api') if pure else 'step_payroll_contracts,step_payroll_enterprise_reference'
        def execute(name,flags):
            with (stage/(name+'-bootstrap.log')).open('w') as stream:
                status=subprocess.run(base+opts+flags+['--logfile='+str(stage/(name+'.log')),'--stop-after-init'],stdout=stream,stderr=subprocess.STDOUT)
            text=(stage/(name+'.log')).read_text(errors='replace')
            print('\n'.join(l for l in text.splitlines() if ' ERROR ' in l or ' CRITICAL ' in l or 'tests.result' in l)[-7000:],flush=True)
            assert status.returncode==0 and not re.search(r' (ERROR|CRITICAL) ',text),str(stage/(name+'.log'))
            return text
        if not pure:
            execute('upgrade',['-i',modules])
            upgraded=preservation.snapshot(args.database);dump_json('business-after-upgrade',upgraded)
            assert same_values(baseline,upgraded),'Upgrade changed original data/counters'
        if args.profile=='simpledigital':
            execute('provider-install',['-i',modules])
            print('PROVIDER_REGISTRY_OK '+args.mode,flush=True)
            return
        text=execute('tests',['-i' if pure else '-u',modules,'--test-enable','--test-tags='+('/payroll,/payroll_account,/step_payroll_oca_api' if pure else '/step_payroll_enterprise_reference')])
        assert re.search(r'0 failed, 0 error\(s\) of '+str(68 if pure else 15)+r' tests',text), 'Expected all upstream and shared API contracts to run'
        if not pure:
            after=preservation.snapshot(args.database);current=preservation.identity_contract(args.database)
            dump_json('business-after',after);dump_json('identity-after',current);dump_json('history-after',preservation.history_contract(args.database))
            assert same_values(baseline,after),'Original business data/counters changed after reference tests'
            for name,rows in original.items():
                if rows and 'id' in rows[0]:
                    now={r['id']:r for r in current[name]}
                    assert all(now.get(r['id'])==r for r in rows),(name,'Original metadata changed')
                else:assert all(row in current[name] for row in rows),name
            assert preservation.history_contract(args.database)==history
            assert runtime_contract(conf)==contract,'Active source configuration/versions changed'
        assert all(hashlib.sha256((source/key).read_bytes()).hexdigest()==value for key,value in fp.items())
        counts=json.loads(sql(args.database,"SELECT json_build_object('installed',count(*),'enterprise',count(*) FILTER (WHERE license='OEEL-1')) FROM ir_module_module WHERE state='installed'"))
        if pure:assert counts['enterprise']==0
        dump_json('passed',{'mode':args.mode,'database':args.database,'writes_to_source':False,'package_files':len(fp),
            'source_files_sha256':hashlib.sha256((stage/'source-files.json').read_bytes()).hexdigest(),
            'counts':counts,'oca_revision':PIN,'official_community_revision':OFFICIAL_PIN if pure else None,'historical_conversion':False,'simpledigital_certified':False,
            'test_results':[l for l in text.splitlines() if 'tests.result' in l],
            'validator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
        print('PAYROLL_API_OK '+args.mode,flush=True)


if __name__=='__main__':main()
