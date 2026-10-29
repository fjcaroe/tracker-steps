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
    parser.add_argument('--profile',choices=('api','simpledigital','previred','previred-standalone','previred-simpledigital','book-consumers','book-install','book-history'),default='api')
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--database',required=True)
    parser.add_argument('--tablespace')
    parser.add_argument('--accelerated',action='store_true',help='Install the exact HR, banking and CAF package together')
    parser.add_argument('--runtime',type=Path,required=True)
    parser.add_argument('--oca',type=Path,required=True)
    args=parser.parse_args()
    full_book=args.profile in ('book-install','book-history')
    binary_book=args.profile=='book-install'
    own_book=args.profile in ('book-consumers','book-install','book-history')
    simpledigital=args.profile in ('simpledigital','previred','previred-simpledigital','book-consumers','book-install','book-history')
    previred=args.profile in ('previred','previred-simpledigital','book-consumers','book-install','book-history')
    bridge=args.profile in ('previred-simpledigital','book-consumers','book-install','book-history')
    standalone=args.profile=='previred-standalone'
    if simpledigital:
        MODULES=MODULES+('step_simpledigital_oca_base','step_simpledigital_oca_security','l10n_cl_simpledigital_payroll')
    if previred:MODULES+=('step_hr_previred',)
    if bridge:MODULES+=('step_hr_previred_simpledigital',)
    if own_book:MODULES+=('step_hr_remuneration_book',)
    if standalone:
        assert args.mode=='community'
        MODULES=('step_payroll_contracts','step_hr_previred')
    if args.accelerated:
        assert args.profile=='simpledigital'
        sys.path.insert(0,str(args.root/'addons/tools/community'))
        from accelerated_acceptance import HR_MODULES,HR_TEST_COUNT,HR_TEST_TAGS,prepare_hr_overlay
        from finance_frontier_contract import metadata_snapshot,verify_metadata
        finance_modules=('step_accounting_multicurrency_core','step_account_balance_analytic',
                         'step_bank_export_core','step_account_treasury_batch','step_bank_security')
        MODULES+=HR_MODULES+finance_modules+('step_l10n_cl_edi_core',)
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
    hr_overlay=None
    if args.accelerated:
        # Generic consumer sources are in the identical packet; the only CE
        # derivation is separately fingerprinted before any registry is loaded.
        if pure:
            for m in HR_MODULES+('step_account_treasury_batch','step_bank_security'):
                (overlay/m).unlink()
        hr_overlay=prepare_hr_overlay(source,stage,overlay,community=pure)
        dump_candidate={str(p.relative_to(hr_overlay if pure else source)):hashlib.sha256(p.read_bytes()).hexdigest()
            for m in HR_MODULES for p in sorted(((hr_overlay if pure else source)/m).rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts}
        (stage/'consumer-source-files.json').write_text(json.dumps(dump_candidate,indent=2))
        if not pure:
            for m in finance_modules+('step_l10n_cl_edi_core',):
                (overlay/m).symlink_to(source/m)
    if own_book and args.mode!='community':(overlay/'step_hr_remuneration_book').symlink_to(source/'step_hr_remuneration_book')
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
        if args.accelerated:
            for table in ('res_partner_bank','res_bank'):
                result[table]=json.loads(sql(args.database,"SELECT json_build_object('rows',count(*),'hash',md5(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),''))) FROM "+table+' t'))
        if simpledigital:
            result['rule_group_rel']=json.loads(sql(args.database,"SELECT json_build_object('rows',count(*),'hash',md5(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),''))) FROM rule_group_rel t WHERE rule_group_id NOT IN (SELECT res_id FROM ir_model_data WHERE module='step_simpledigital_oca_security' AND model='ir.rule')"))
        return result
    with open('/run/lock/steps-environments.lock','a') as lock:
        print('PAYROLL_API_WAITING_FOR_SHARED_LEASE '+args.mode,flush=True);fcntl.flock(lock,fcntl.LOCK_EX)
        assert not sql('postgres',"SELECT 1 FROM pg_database WHERE datname='"+args.database+"'")
        # PostgreSQL can live on a separate volume from /opt; check both under
        # the shared lease before creating or restoring another private clone.
        pgstat=os.statvfs(sql('postgres','SHOW data_directory'))
        rootstat=os.statvfs(root)
        capacity={'postgres_available_bytes':pgstat.f_bavail*pgstat.f_frsize,
            'artifact_available_bytes':rootstat.f_bavail*rootstat.f_frsize,
            'postgres_minimum_bytes':5*1024**3,'artifact_minimum_bytes':2*1024**3}
        dump_json('storage-preflight',capacity)
        assert capacity['postgres_available_bytes']>=capacity['postgres_minimum_bytes'],'PostgreSQL volume reserve too low; retire owned rehearsals before continuing'
        assert capacity['artifact_available_bytes']>=capacity['artifact_minimum_bytes'],'Private artifact volume reserve too low'
        create=['sudo','-u','postgres','createdb','--owner='+config['options']['db_user']]
        if args.tablespace:
            expected='steps_community_storage_20261028_'+('community' if pure else 'cerro')
            assert args.tablespace==expected
            location=sql('postgres',"SELECT pg_tablespace_location(oid) FROM pg_tablespace WHERE spcname='"+expected+"'")
            assert location=='/opt/steps-validation/community-payroll-storage-20261028/'+('community' if pure else 'cerro')
            assert sql('postgres',"SELECT pg_get_userbyid(spcowner) FROM pg_tablespace WHERE spcname='"+expected+"'")==config['options']['db_user']
            capacity['validation_tablespace']={'name':expected,'location':location}
            dump_json('storage-preflight',capacity)
            create+=['--tablespace='+expected]
        run(*create,args.database)
        baseline=original=history=contract=None
        if not pure:
            assert config['options']['db_name']=='CERRO_EL_PLOMO'
            with (stage/'source.dump').open('wb') as out:run('sudo','-u','postgres','pg_dump','-Fc','CERRO_EL_PLOMO',stdout=out)
            with (stage/'source.dump').open('rb') as inp,(stage/'restore.log').open('w') as restore_log:
                run('sudo','-u','postgres','pg_restore','--exit-on-error','--no-owner','--no-acl','--no-comments',*(['--no-tablespaces'] if args.tablespace else []),'--role='+config['options']['db_user'],'-d',args.database,stdin=inp,stderr=restore_log)
            sql(args.database,'UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false;')
            store=data/'filestore'/args.database;store.mkdir(parents=True)
            run('rsync','-a',str(Path(config['options']['data_dir'])/'filestore/CERRO_EL_PLOMO')+'/',str(store)+'/')
            contract=runtime_contract(conf);dump_json('source-contract',contract)
            baseline=snapshot();original=preservation.identity_contract(args.database);history=preservation.history_contract(args.database)
            if args.accelerated:dump_json('bank-metadata-before',metadata_snapshot(sql,args.database))
            for name,value in [('business-before',baseline),('identity-before',original),('history-before',history)]:dump_json(name,value)
        for p in [stage,*stage.rglob('*')]:
            if not p.is_symlink():os.chown(p,identity.pw_uid,identity.pw_gid)
        with socket.socket() as listener:listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
        paths=(str(hr_overlay)+',' if hr_overlay else '')+str(overlay)+','+(str(args.runtime/'addons') if pure else config['options']['addons_path'])
        entry=args.runtime/'odoo-bin' if pure else source/'tools/ops/run_agriculture_upgrade.py'
        base=['sudo','-u',user,'/usr/bin/python3.10',str(entry)]
        opts=['-c',str(conf),'-d',args.database,'--db-filter=^'+args.database+'$','--addons-path='+paths,
            '--data-dir='+str(data),'--load=base,web','--workers=0','--max-cron-threads=0',
            '--http-interface=127.0.0.1','--http-port='+str(port),'--gevent-port=0','--without-demo='+('' if pure else 'all')]
        modules=('step_simpledigital_oca_security' if simpledigital else 'step_payroll_oca_api') if pure else 'step_payroll_contracts,step_payroll_enterprise_reference'+(',step_simpledigital_oca_security' if simpledigital else '')
        if previred:modules+=',step_hr_previred'
        if bridge:modules+=',step_hr_previred_simpledigital'
        if own_book and (not pure or full_book):modules+=',step_hr_remuneration_book'
        if standalone:modules='step_hr_previred'
        if args.accelerated:
            modules+=','+','.join(HR_MODULES+finance_modules[:3]+('step_l10n_cl_edi_core',))
            if not pure:modules+=',step_account_treasury_batch,step_bank_security'
        execution_env=dict(os.environ)
        if (root/'basis-input.json').exists():
            assert simpledigital
            private_input=stage/'basis-reference-input.json'
            private_input.write_bytes((root/'basis-input.json').read_bytes())
            os.chown(private_input,identity.pw_uid,identity.pw_gid);os.chmod(private_input,0o600)
            execution_env.update(STEPS_PAYROLL_BASIC_REFERENCE_JSON=str(private_input),
                                 STEPS_PAYROLL_BASIC_REFERENCE_OUTPUT=str(stage/'monthly-basis.json'))
        def execute(name,flags):
            command=base+opts+flags+['--logfile='+str(stage/(name+'.log')),'--stop-after-init']
            if (root/'basis-input.json').exists():
                # sudo resets arbitrary environment variables. Pass only these
                # private file paths explicitly, never payroll contents/secrets.
                command=base[:3]+['env',*['%s=%s'%(key,execution_env[key]) for key in
                    ('STEPS_PAYROLL_BASIC_REFERENCE_JSON','STEPS_PAYROLL_BASIC_REFERENCE_OUTPUT')]]+command[3:]
            with (stage/(name+'-bootstrap.log')).open('w') as stream:
                status=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,env=execution_env)
            text=(stage/(name+'.log')).read_text(errors='replace')
            if args.tablespace:
                current=os.statvfs(sql('postgres','SHOW data_directory'))
                assert current.f_bavail*current.f_frsize>=5*1024**3,'PostgreSQL/WAL reserve fell below minimum'
            print('\n'.join(l for l in text.splitlines() if ' ERROR ' in l or ' CRITICAL ' in l or 'tests.result' in l)[-7000:],flush=True)
            assert status.returncode==0 and not re.search(r' (ERROR|CRITICAL) ',text),str(stage/(name+'.log'))
            return text
        if not pure:
            existing=['step_hr_previred']+(['step_hr_previred_simpledigital'] if bridge else []) if previred else []
            if own_book:existing.append('step_hr_remuneration_book')
            if args.accelerated:
                installed=set(sql(args.database,"SELECT name FROM ir_module_module WHERE state='installed'").splitlines())
                existing=[name for name in modules.split(',') if name in installed]
            execute('upgrade',['-i',','.join(name for name in modules.split(',') if name not in existing)]+(['-u',','.join(existing)] if existing else []))
            upgraded=snapshot();dump_json('business-after-upgrade',upgraded)
            assert same_values(baseline,upgraded),'Upgrade changed original data/counters'
        tags=(('/payroll,/payroll_account,/step_payroll_oca_api' if pure else '/step_payroll_enterprise_reference')+(',/step_simpledigital_oca_security:SimpleDigitalBoundary'+(',/step_simpledigital_oca_base' if pure else '') if simpledigital else ''))
        if previred:tags+=',/step_hr_previred:TestCoreIsolation'
        if bridge:
            tags+=',/step_hr_previred_simpledigital:TestSimpleDigitalMatrix,/step_hr_previred_simpledigital:TestSimpleDigitalRouteSecurity'
            methods=('manager_guard_uses_real_role','foreign_and_hidden_salary_are_denied','real_vendor_empty_is_an_error',
                'closed_zero_total_is_authoritative','missing_total_is_rejected','employer_zero_does_not_reconstruct_deduction','paid_state_keeps_original_totals')
            tags+=','+','.join('/step_hr_previred_simpledigital:CommunityBridgeContracts.test_community_'+name for name in methods)
        if standalone:tags='/step_hr_previred:TestCoreIsolation'
        if args.accelerated:
            tags+=','+HR_TEST_TAGS+',/step_bank_export_core,/step_account_balance_analytic,/step_l10n_cl_edi_core'
            if not pure:tags+=',/step_account_treasury_batch,/step_bank_security'
        if own_book:
            methods=['code_snapshots_preserve_original_zero_in_batch','actual_movement_adapter_reads_stored_totals','actual_movement_adapter_rejects_hidden_lines']
            if not pure or full_book:methods.append('native_registered_extractor_uses_original_code_map')
            tags+=','+','.join('/step_simpledigital_oca_security:OwnBookConsumers.test_'+name for name in methods)
        if full_book:
            methods=['real_views_menus_and_actions','real_consolidated_outputs','partial_user_cannot_export_full_book','engine_alias_retirement_preserves_records','pdf_scope_requires_one_readable_wizard','pdf_template_preserves_zero_and_negative_amounts']
            tags+=','+','.join('/step_simpledigital_oca_security:FullBookInstall.test_'+name for name in methods)
        if binary_book:
            methods=['signed_xlsx_response_and_audit','tampered_links_rejected','foreign_owner_rejected','hidden_line_denied_without_report','official_csv_policy_over_http','dashboard_rpc_uses_real_engine_actions','actual_pdf_binary_and_employee_sheets']
            tags+=','+','.join('/step_simpledigital_oca_security:FullBookHttp.test_'+name for name in methods)
        text=execute('tests',['-i' if pure else '-u',modules,'--test-enable','--test-tags='+tags])
        expected=7 if standalone else (85 if pure else 25)+((54 if pure else 47) if simpledigital else 0)+(7 if previred else 0)+(26 if bridge else 0)+((4 if full_book or not pure else 3) if own_book else 0)+(6 if full_book else 0)+(7 if binary_book else 0)
        if args.accelerated:expected+=HR_TEST_COUNT+19+18+(0 if pure else 38)
        assert re.search(r'0 failed, 0 error\(s\) of '+str(expected)+r' tests',text), 'Expected all upstream and shared API contracts to run'
        if simpledigital:
            probe=source/'tools/community/inspect_payroll_configuration.py'
            expression="import runpy; runpy.run_path("+repr(str(probe))+")["+repr('inspect')+"](env,"+repr(str(stage/'configuration.json'))+")"
            with (stage/'configuration-bootstrap.log').open('w') as stream:
                status=subprocess.run(base+['shell']+opts+['--no-http','--logfile='+str(stage/'configuration.log')],
                    input=expression,text=True,stdout=stream,stderr=subprocess.STDOUT)
            report_log=(stage/'configuration.log').read_text(errors='replace')
            assert status.returncode==0 and not re.search(r' (ERROR|CRITICAL) ',report_log),'Configuration inspector failed'
        if args.accelerated:
            checker=source/'tools/community/finance_frontier_contract.py'
            expression="import runpy,json; proof=runpy.run_path("+repr(str(checker))+")[\"verify\"](env,"+repr('community' if pure else 'cerro-copy')+");open("+repr(str(stage/'finance-frontier.json'))+",'w').write(json.dumps(proof,indent=2))"
            with (stage/'finance-bootstrap.log').open('w') as stream:
                status=subprocess.run(base+['shell']+opts+['--no-http','--logfile='+str(stage/'finance.log')],input=expression,text=True,stdout=stream,stderr=subprocess.STDOUT)
            report_log=(stage/'finance.log').read_text(errors='replace')
            assert status.returncode==0 and not re.search(r' (ERROR|CRITICAL) ',report_log) and (stage/'finance-frontier.json').exists(),'Finance registry contract failed'
        if (root/'basis-input.json').exists():
            replay=json.loads((stage/'monthly-basis.json').read_text())
            assert replay['basic_matches_original_snapshot'] and replay['transaction_case'] and replay['normal_actor']
            remaining=json.loads(sql(args.database,"SELECT json_build_object('companies',(SELECT count(*) FROM res_company WHERE name='Private payroll API fixture'),'users',(SELECT count(*) FROM res_users WHERE login='private-payroll-api-manager'))"))
            assert remaining=={'companies':0,'users':0},'Transactional payroll fixture leaked'
            replay.update(fixtures_rolled_back=True,rollback_verified=True,fixture_master_counts=remaining)
            dump_json('monthly-basis',replay)
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
            if args.accelerated:
                bank_after=metadata_snapshot(sql,args.database);dump_json('bank-metadata-after',bank_after)
                dump_json('bank-metadata-proof',verify_metadata(json.loads((stage/'bank-metadata-before.json').read_text()),bank_after))
            assert runtime_contract(conf)==contract,'Active source configuration/versions changed'
        assert all(hashlib.sha256((source/key).read_bytes()).hexdigest()==value for key,value in fp.items())
        counts=json.loads(sql(args.database,"SELECT json_build_object('installed',count(*),'enterprise',count(*) FILTER (WHERE license='OEEL-1')) FROM ir_module_module WHERE state='installed'"))
        if pure:assert counts['enterprise']==0
        book_installed=sql(args.database,"SELECT count(*) FROM ir_module_module WHERE name='step_hr_remuneration_book' AND state='installed'")=='1'
        if own_book:
            assert book_installed==bool(not pure or full_book),'Distinguish Community library tests from native full-module upgrade'
            if not pure:assert sql(args.database,"SELECT latest_version FROM ir_module_module WHERE name='step_hr_remuneration_book'")=='18.0.3.5.2'

        if binary_book:
            pdfs=json.loads((stage/'pdf-evidence/pdf-proof.json').read_text())
            assert {row['report'] for row in pdfs}=={'consolidated_book','employee_sheets'}
            assert len(pdfs)==2 and all(row['normal_actor'] and row['single_audit'] and row['history_preserved'] for row in pdfs)
            assert all(hashlib.sha256((stage/'pdf-evidence'/(row['report']+'.pdf')).read_bytes()).hexdigest()==row['sha256'] for row in pdfs)

        engine_models=int(sql(args.database,"SELECT count(*) FROM ir_model WHERE model='hr.payslip'"))
        if standalone:
            assert engine_models==0 and sql(args.database,"SELECT count(*) FROM ir_module_module WHERE name IN ('payroll','hr_payroll') AND state='installed'")=='0'
        if previred or standalone:assert sql(args.database,"SELECT latest_version FROM ir_module_module WHERE name='step_hr_previred' AND state='installed'")=='18.0.3.8.8'
        if bridge:assert sql(args.database,"SELECT latest_version FROM ir_module_module WHERE name='step_hr_previred_simpledigital' AND state='installed'")=='18.0.2.4.2'
        dump_json('passed',{'mode':args.mode,'profile':args.profile,'accelerated':args.accelerated,'database':args.database,'writes_to_source':False,'package_files':len(fp),
            'source_files_sha256':hashlib.sha256((stage/'source-files.json').read_bytes()).hexdigest(),
            'counts':counts,'pdf_binary_reports':2 if binary_book else 0,'own_book_installed':book_installed,'own_book_library_only':bool(own_book and pure and not full_book),'payroll_model_registered':bool(engine_models),'oca_revision':PIN,'official_community_revision':OFFICIAL_PIN if pure else None,'historical_conversion':False,'simpledigital_certified':False,
            'test_results':[l for l in text.splitlines() if 'tests.result' in l],
            'expected_test_count':expected,
            'accelerated_tools_sha256':{name:hashlib.sha256((source/'tools/community'/name).read_bytes()).hexdigest() for name in ('accelerated_acceptance.py','hr_consumers_candidate.py','finance_frontier_contract.py')} if args.accelerated else {},
            'validator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
        print('PAYROLL_API_OK '+args.mode,flush=True)


if __name__=='__main__':main()
