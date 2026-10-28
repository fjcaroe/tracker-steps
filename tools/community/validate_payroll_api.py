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
    parser.add_argument('--profile',choices=('api','simpledigital','previred','previred-standalone','previred-simpledigital'),default='api')
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--database',required=True)
    parser.add_argument('--runtime',type=Path,required=True)
    parser.add_argument('--oca',type=Path,required=True)
    args=parser.parse_args()
    simpledigital=args.profile in ('simpledigital','previred','previred-simpledigital')
    previred=args.profile in ('previred','previred-simpledigital')
    bridge=args.profile=='previred-simpledigital'
    standalone=args.profile=='previred-standalone'
    if simpledigital:
        MODULES=MODULES+('step_simpledigital_oca_base','step_simpledigital_oca_security','l10n_cl_simpledigital_payroll')
    if previred:MODULES+=('step_hr_previred',)
    if bridge:MODULES+=('step_hr_previred_simpledigital',)
    if standalone:
        assert args.mode=='community'
        MODULES=('step_payroll_contracts','step_hr_previred')
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
    for m in (tuple(m for m in MODULES if m!='step_payroll_enterprise_reference') if pure else ((MODULES[0],MODULES[2],'step_simpledigital_oca_security')+(('step_hr_previred',) if previred else ())+(('step_hr_previred_simpledigital',) if bridge else ()) if simpledigital else (MODULES[0],MODULES[2]))):(overlay/m).symlink_to(source/m)
    sys.path.insert(0,str(source/'tools/community'))
    import validate_agriculture_core as preservation
    preservation.MODULES=preservation.BASE_MODULES+preservation.PRODUCER_MODULES+preservation.OPERATIONS_MODULES+preservation.LABOR_MODULES+preservation.HARVEST_MODULES+preservation.HR_MODULES
    from validate_community_reports import sql,same_values
    from manage_community_reports import runtime_contract as original_runtime_contract
    def runtime_contract(conf):
        value=original_runtime_contract(conf)
        if simpledigital:
            roots=[Path(p.strip()) for p in config['options']['addons_path'].split(',')]
            provider=next(p/'l10n_cl_simpledigital_payroll' for p in roots if (p/'l10n_cl_simpledigital_payroll/__manifest__.py').exists())
            pin=json.loads((source/'tools/community/simpledigital_runtime_source.json').read_text(encoding='utf-8'))
            actual={name:hashlib.sha256((provider/name).read_bytes()).hexdigest() for name in pin['files']}
            assert actual==pin['files'],'Active provider drift from audited source'
            value['simpledigital_original_files']=actual
        return value
    def dump_json(name,value):(stage/(name+'.json')).write_text(json.dumps(value,indent=2))
    if pure:
        for path,url in ((args.runtime,'https://github.com/odoo/odoo.git'),(args.oca,'https://github.com/OCA/payroll.git')):
            assert run('git','-C',str(path),'remote','get-url','origin',capture_output=True,text=True).stdout.strip()==url
            assert not run('git','-C',str(path),'status','--porcelain',capture_output=True,text=True).stdout.strip()
        assert run('git','-C',str(args.runtime),'rev-parse','HEAD',capture_output=True,text=True).stdout.strip()==OFFICIAL_PIN
        assert run('git','-C',str(args.oca),'rev-parse','HEAD',capture_output=True,text=True).stdout.strip()==PIN
        if not standalone:
            for m in ('payroll','payroll_account'):(overlay/m).symlink_to(args.oca/m)
        dump_json('vendor-files',{str(p.relative_to(args.oca)):hashlib.sha256(p.read_bytes()).hexdigest()
            for m in ('payroll','payroll_account') for p in sorted((args.oca/m).rglob('*')) if p.is_file() and '__pycache__' not in p.parts})
    def snapshot():
        result=preservation.snapshot(args.database)
        if simpledigital:
            result['rule_group_rel']=json.loads(sql(args.database,"SELECT json_build_object('rows',count(*),'hash',md5(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),''))) FROM rule_group_rel t WHERE rule_group_id NOT IN (SELECT res_id FROM ir_model_data WHERE module='step_simpledigital_oca_security' AND model='ir.rule')"))
        return result
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
            baseline=snapshot();original=preservation.identity_contract(args.database);history=preservation.history_contract(args.database)
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
        modules=('step_simpledigital_oca_security' if simpledigital else 'step_payroll_oca_api') if pure else 'step_payroll_contracts,step_payroll_enterprise_reference'+(',step_simpledigital_oca_security' if simpledigital else '')
        if previred:modules+=',step_hr_previred'
        if bridge:modules+=',step_hr_previred_simpledigital'
        if standalone:modules='step_hr_previred'
        def execute(name,flags):
            with (stage/(name+'-bootstrap.log')).open('w') as stream:
                status=subprocess.run(base+opts+flags+['--logfile='+str(stage/(name+'.log')),'--stop-after-init'],stdout=stream,stderr=subprocess.STDOUT)
            text=(stage/(name+'.log')).read_text(errors='replace')
            print('\n'.join(l for l in text.splitlines() if ' ERROR ' in l or ' CRITICAL ' in l or 'tests.result' in l)[-7000:],flush=True)
            assert status.returncode==0 and not re.search(r' (ERROR|CRITICAL) ',text),str(stage/(name+'.log'))
            return text
        if not pure:
            existing=['step_hr_previred']+(['step_hr_previred_simpledigital'] if bridge else []) if previred else []
            execute('upgrade',['-i',','.join(name for name in modules.split(',') if name not in existing)]+(['-u',','.join(existing)] if existing else []))
            upgraded=snapshot();dump_json('business-after-upgrade',upgraded)
            assert same_values(baseline,upgraded),'Upgrade changed original data/counters'
        tags=(('/payroll,/payroll_account,/step_payroll_oca_api' if pure else '/step_payroll_enterprise_reference')+(',/step_simpledigital_oca_security'+(',/step_simpledigital_oca_base' if pure else '') if simpledigital else ''))
        if previred:tags+=',/step_hr_previred:TestCoreIsolation'
        if bridge:
            tags+=',/step_hr_previred_simpledigital:TestSimpleDigitalMatrix,/step_hr_previred_simpledigital:TestSimpleDigitalRouteSecurity'
            methods=('manager_guard_uses_real_role','foreign_and_hidden_salary_are_denied','real_vendor_empty_is_an_error',
                'closed_zero_total_is_authoritative','missing_total_is_rejected','employer_zero_does_not_reconstruct_deduction','paid_state_keeps_original_totals')
            tags+=','+','.join('/step_hr_previred_simpledigital:CommunityBridgeContracts.test_community_'+name for name in methods)
        if standalone:tags='/step_hr_previred:TestCoreIsolation'
        text=execute('tests',['-i' if pure else '-u',modules,'--test-enable','--test-tags='+tags])
        expected=7 if standalone else (68 if pure else 15)+((38 if pure else 31) if simpledigital else 0)+(7 if previred else 0)+(26 if bridge else 0)
        assert re.search(r'0 failed, 0 error\(s\) of '+str(expected)+r' tests',text), 'Expected all upstream and shared API contracts to run'
        if simpledigital:
            probe=source/'tools/community/inspect_payroll_configuration.py'
            expression="import runpy; runpy.run_path("+repr(str(probe))+")["+repr('inspect')+"](env,"+repr(str(stage/'configuration.json'))+")"
            with (stage/'configuration-bootstrap.log').open('w') as stream:
                status=subprocess.run(base+['shell']+opts+['--no-http','--logfile='+str(stage/'configuration.log')],
                    input=expression,text=True,stdout=stream,stderr=subprocess.STDOUT)
            report_log=(stage/'configuration.log').read_text(errors='replace')
            assert status.returncode==0 and not re.search(r' (ERROR|CRITICAL) ',report_log),'Configuration inspector failed'
        if not pure:
            after=snapshot();current=preservation.identity_contract(args.database)
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
        engine_models=int(sql(args.database,"SELECT count(*) FROM ir_model WHERE model='hr.payslip'"))
        if standalone:
            assert engine_models==0 and sql(args.database,"SELECT count(*) FROM ir_module_module WHERE name IN ('payroll','hr_payroll') AND state='installed'")=='0'
        if previred or standalone:assert sql(args.database,"SELECT latest_version FROM ir_module_module WHERE name='step_hr_previred' AND state='installed'")=='18.0.3.8.8'
        if bridge:assert sql(args.database,"SELECT latest_version FROM ir_module_module WHERE name='step_hr_previred_simpledigital' AND state='installed'")=='18.0.2.4.2'
        dump_json('passed',{'mode':args.mode,'profile':args.profile,'database':args.database,'writes_to_source':False,'package_files':len(fp),
            'source_files_sha256':hashlib.sha256((stage/'source-files.json').read_bytes()).hexdigest(),
            'counts':counts,'payroll_model_registered':bool(engine_models),'oca_revision':PIN,'official_community_revision':OFFICIAL_PIN if pure else None,'historical_conversion':False,'simpledigital_certified':False,
            'test_results':[l for l in text.splitlines() if 'tests.result' in l],
            'validator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
        print('PAYROLL_API_OK '+args.mode,flush=True)


if __name__=='__main__':main()
