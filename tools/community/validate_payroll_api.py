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
from offline_process import offline_odoo

MODULES=('step_payroll_contracts','step_payroll_oca_api','step_payroll_enterprise_reference')
OFFICIAL_PIN='4b4efe68291d6def5bb7d2e1f2b829e0cda577d4'
PIN='4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e'


def run(*args,**kw):return subprocess.run(args,check=True,**kw)


def concrete_test_count(source, module):
    return sum(1 for path in (source/module/'tests').glob('test_*.py')
        for cls in ast.parse(path.read_text(encoding='utf-8-sig')).body if isinstance(cls,ast.ClassDef)
        for method in cls.body if isinstance(method,ast.FunctionDef) and method.name.startswith('test_'))


def main():
    global MODULES
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('community','cerro-reference'))
    parser.add_argument('--profile',choices=('api','simpledigital','previred','previred-standalone','previred-simpledigital','book-consumers','book-install','book-history'),default='api')
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--database',required=True)
    parser.add_argument('--tablespace')
    parser.add_argument('--multifront',action='store_true',help='Treasury launchers, approved contract days and real TED validation')
    parser.add_argument('--focused-multifront',action='store_true',help='Community development pass for the changed functional contracts')
    parser.add_argument('--numeric-input-engine', action='store_true', help='Pinned LGPL real-engine overlay: NUMERIC amount from first init')
    parser.add_argument('--accelerated',action='store_true',help='Install the exact HR, banking and CAF package together')
    parser.add_argument('--custody-grouping',action='store_true',help='Include real CAF custody and draft payment grouping providers')
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
    assert not args.focused_multifront or (args.multifront and args.mode=='community')
    assert not args.multifront or (args.accelerated and args.custody_grouping and simpledigital)
    assert not args.numeric_input_engine or (args.mode == 'community' and not standalone)
    assert not args.custody_grouping or args.accelerated
    custody_modules=('step_l10n_cl_caf_custody_core','step_l10n_cl_caf_storage','step_l10n_cl_caf_native_reference')
    grouping_modules=('step_batch_payment_grouping','step_batch_payment_core')
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
        from hr_consumer_metadata import verify as verify_hr_metadata
        finance_modules=('step_accounting_multicurrency_core','step_account_balance_analytic',
                         'step_bank_export_core','step_account_treasury_batch','step_bank_security',
                         'step_accounting_multicurrency')
        MODULES+=HR_MODULES+finance_modules+('step_l10n_cl_edi_core',)
        if args.custody_grouping:MODULES+=custody_modules+grouping_modules
    treasury_modules=('step_account_treasury','step_treasury_community_reports','step_account_treasury_reports')
    if args.multifront:
        MODULES+=treasury_modules+('step_hr_contract_days','step_hr_contract_days_oca')
        from treasury_launcher_contract import snapshot as treasury_snapshot,verify as verify_treasury
    assert os.geteuid()==0 and str(args.root.resolve()).startswith('/opt/steps-validation/')
    assert re.fullmatch(('COMMUNITY_PAYROLL_API_' if args.mode=='community' else 'MANAGEMENT_QA_CERRO_PAYROLL_API_')+'[A-Za-z0-9_]+',args.database)
    root=args.root.resolve();source=root/'addons';stage=root/args.mode
    assert not stage.exists();stage.mkdir(mode=0o750)
    fp={str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for m in MODULES
        for p in sorted((source/m).rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
    assert all((source/m/'__manifest__.py').exists() for m in MODULES)
    api_test_count=concrete_test_count(source,'step_payroll_oca_api')
    reference_test_count=concrete_test_count(source,'step_payroll_enterprise_reference')
    base_test_count=concrete_test_count(source,'step_simpledigital_oca_base') if simpledigital else 0
    dte_test_count=concrete_test_count(source,'step_l10n_cl_edi_core') if args.accelerated else 0
    (stage/'source-files.json').write_text(json.dumps(fp,indent=2))
    pure=args.mode=='community';conf=Path('/etc/dev_odoo18.conf' if pure else '/etc/odoo18-cerroelplomo.conf')
    config=configparser.ConfigParser(interpolation=None);assert config.read(conf)
    user='odoo' if pure else 'cerro_odoo18';identity=pwd.getpwnam(user)
    data=stage/'data';data.mkdir();overlay=stage/'addons';overlay.mkdir()
    for m in (tuple(m for m in MODULES if m not in ('step_payroll_enterprise_reference','step_l10n_cl_caf_native_reference')) if pure else ((MODULES[0],MODULES[2],'step_simpledigital_oca_security')+(('step_hr_previred',) if previred else ())+(('step_hr_previred_simpledigital',) if bridge else ()) if simpledigital else (MODULES[0],MODULES[2]))):(overlay/m).symlink_to(source/m)
    hr_overlay=None
    if args.accelerated:
        # Generic consumer sources are in the identical packet; the only CE
        # derivation is separately fingerprinted before any registry is loaded.
        if pure:
            for m in HR_MODULES+('step_account_treasury_batch','step_bank_security','step_accounting_multicurrency'):
                (overlay/m).unlink()
        hr_overlay=prepare_hr_overlay(source,stage,overlay,community=pure)
        dump_candidate={str(p.relative_to(hr_overlay if pure else source)):hashlib.sha256(p.read_bytes()).hexdigest()
            for m in HR_MODULES for p in sorted(((hr_overlay if pure else source)/m).rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts}
        (stage/'consumer-source-files.json').write_text(json.dumps(dump_candidate,indent=2))
        if not pure:
            for m in finance_modules+('step_l10n_cl_edi_core',):
                (overlay/m).symlink_to(source/m)
            if args.custody_grouping:
                for m in ('step_l10n_cl_caf_custody_core','step_l10n_cl_caf_native_reference','step_batch_payment_grouping'):
                    (overlay/m).symlink_to(source/m)
    if args.multifront and not pure:
        for m in treasury_modules+('step_hr_contract_days',):(overlay/m).symlink_to(source/m)
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
            engine_root = args.oca
            if args.numeric_input_engine:
                from build_numeric_input_engine import build as build_numeric, verify as verify_numeric
                numeric_root = root / 'engine-addons'
                if numeric_root.exists():verify_numeric(args.oca, numeric_root)
                else:build_numeric(args.oca, numeric_root)
                engine_root = numeric_root
            for m in ('payroll','payroll_account'):
                (overlay/m).symlink_to((engine_root if m == 'payroll' else args.oca)/m)
        dump_json('vendor-files',{str(p.relative_to(args.oca)):hashlib.sha256(p.read_bytes()).hexdigest()
            for m in ('payroll','payroll_account') for p in sorted((args.oca/m).rglob('*')) if p.is_file() and '__pycache__' not in p.parts})
    def snapshot():
        result=preservation.snapshot(args.database)
        if args.accelerated:
            # These two new transient containers have no historical business
            # rows. Every original table remains under the exact comparison.
            for table in ('step_bank_export_wizard','step_bank_export_wizard_payment_rel'):
                if table in result:
                    assert result[table]['rows']==0,'Bank export fixture leaked'
                    result.pop(table)
            for table in ('res_partner_bank','res_bank'):
                result[table]=json.loads(sql(args.database,"SELECT json_build_object('rows',count(*),'hash',md5(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),''))) FROM "+table+' t'))
            result['ir_ui_menu_group_rel']=json.loads(sql(args.database,
                "SELECT json_build_object('rows',count(*),'hash',md5(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),''))) FROM ir_ui_menu_group_rel t WHERE menu_id NOT IN (SELECT res_id FROM ir_model_data WHERE model='ir.ui.menu' AND (module IN ('step_agriculture_core','step_labor_operations_core') OR (module='step_bank_export_core' AND name='menu_bank_export_wizard')))"))
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
            if args.multifront:dump_json('treasury-before',treasury_snapshot(sql,args.database))
            for name,value in [('business-before',baseline),('identity-before',original),('history-before',history)]:dump_json(name,value)
        for p in [stage,*stage.rglob('*')]:
            if not p.is_symlink():os.chown(p,identity.pw_uid,identity.pw_gid)
        with socket.socket() as listener:listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
        paths=(str(hr_overlay)+',' if hr_overlay else '')+str(overlay)+','+(str(args.runtime/'addons') if pure else config['options']['addons_path'])
        entry=args.runtime/'odoo-bin' if pure else source/'tools/ops/run_agriculture_upgrade.py'
        base=['sudo','-u',user,'/usr/bin/python3.10',str(entry)]
        opts=['-c',str(conf),'-d',args.database,'--db-filter=^'+args.database+'$','--addons-path='+paths,
            '--db_host=/var/run/postgresql',
            '--data-dir='+str(data),'--load=base,web','--workers=0','--max-cron-threads=0',
            '--http-interface=127.0.0.1','--http-port='+str(port),'--gevent-port=0','--without-demo='+('' if pure else 'all')]
        modules=('step_simpledigital_oca_security' if simpledigital else 'step_payroll_oca_api') if pure else 'step_payroll_contracts,step_payroll_enterprise_reference'+(',step_simpledigital_oca_security' if simpledigital else '')
        if previred:modules+=',step_hr_previred'
        if bridge:modules+=',step_hr_previred_simpledigital'
        if own_book and (not pure or full_book):modules+=',step_hr_remuneration_book'
        if standalone:modules='step_hr_previred'
        if args.accelerated:
            modules+=','+','.join(HR_MODULES+finance_modules[:3]+('step_l10n_cl_edi_core',))
            if not pure:modules+=',step_account_treasury_batch,step_bank_security,step_accounting_multicurrency'
        if args.custody_grouping:
            modules+=',step_batch_payment_grouping,'+('step_batch_payment_core,step_l10n_cl_caf_storage' if pure else 'step_l10n_cl_caf_native_reference')
        if args.multifront:modules+=','+','.join(treasury_modules)+','+('step_hr_contract_days_oca' if pure else 'step_hr_contract_days')
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
                status=subprocess.run(offline_odoo(command),stdout=stream,stderr=subprocess.STDOUT,env=execution_env)
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
                from packaging.version import Version
                deployed=json.loads(sql(args.database,"SELECT json_object_agg(name,latest_version) FROM ir_module_module WHERE state='installed'"))
                admission={}
                for name in existing:
                    candidate=ast.literal_eval((source/name/'__manifest__.py').read_text(encoding='utf-8-sig'))['version']
                    assert deployed[name] and Version(candidate)>=Version(deployed[name]),'Candidate downgrade refused: '+name
                    admission[name]={'original':deployed[name],'candidate':candidate,'downgrade':False}
                dump_json('version-admission',admission)
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
        if args.multifront:
            tags+=','+','.join('/'+m for m in treasury_modules)+',/step_hr_contract_days'
            if pure:tags+=',/step_hr_contract_days_oca'
        if standalone:tags='/step_hr_previred:TestCoreIsolation'
        if args.accelerated:
            tags+=','+HR_TEST_TAGS+',/step_bank_export_core,/step_account_balance_analytic,/step_l10n_cl_edi_core,/step_accounting_multicurrency_core'
            if not pure:tags+=',/step_account_treasury_batch,/step_bank_security'
        if args.custody_grouping:
            tags+=',/step_batch_payment_grouping,'+('/step_batch_payment_core,/step_l10n_cl_caf_storage' if pure else '/step_l10n_cl_caf_native_reference')
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
        if args.focused_multifront:
            tags=('/step_payroll_oca_api:SavedInputValuesCase,/step_payroll_oca_api:OriginalInputStorageCase,'
                  '/step_payroll_oca_api:OriginalRuleProjectionCase,/step_simpledigital_oca_base:ExistingDraftBatchCase,'
                  '/step_l10n_cl_edi_core:TestTEDCore,/step_l10n_cl_caf_storage:TestTEDCustodyStorage,'
                  '/step_hr_contract_days,/step_hr_contract_days_oca,'+','.join('/'+m for m in treasury_modules))
        text=execute('tests',['-i' if pure else '-u',modules,'--test-enable','--test-tags='+tags])
        stored_pdf_count=0
        if pure and simpledigital and not args.focused_multifront and (source/'step_simpledigital_oca_base/tests/test_report_pdf.py').exists():
            pdf_directory=data/'payslip-pdf-evidence'
            proofs=[row for path in pdf_directory.glob('proof-*.json') for row in json.loads(path.read_text())]
            assert len(proofs)==2,'Both actual stored-line payslip PDF fixtures must run'
            for row in proofs:
                assert row['normal_employee'] and row['stored_history_unchanged'] and not row['missing_assets']
                assert Path(row['file']).name==row['file'] and row['pages']>0
                assert hashlib.sha256((pdf_directory/row['file']).read_bytes()).hexdigest()==row['sha256']
            stored_pdf_count=len(proofs)
            dump_json('stored-payslip-pdf',{'actual_pdf_count':stored_pdf_count,'proofs':proofs,'financial_certified':False})
        expected=7 if standalone else ((38+api_test_count) if pure else reference_test_count)+((48+base_test_count if pure else 48) if simpledigital else 0)+(7 if previred else 0)+(26 if bridge else 0)+((4 if full_book or not pure else 3) if own_book else 0)+(6 if full_book else 0)+(7 if binary_book else 0)
        if args.accelerated:expected+=HR_TEST_COUNT+33+dte_test_count+11+(0 if pure else 39)
        if args.custody_grouping:
            expected+=concrete_test_count(source,'step_l10n_cl_caf_storage' if pure else 'step_l10n_cl_caf_native_reference')+concrete_test_count(source,'step_batch_payment_grouping')+(concrete_test_count(source,'step_batch_payment_core') if pure else 0)
        if args.multifront:
            expected+=sum(concrete_test_count(source,m) for m in treasury_modules)+concrete_test_count(source,'step_hr_contract_days')+(concrete_test_count(source,'step_hr_contract_days_oca') if pure else 0)
        if args.focused_multifront:expected=128
        assert re.search(r'0 failed, 0 error\(s\) of '+str(expected)+r' tests',text), 'Expected all upstream and shared API contracts to run'
        if simpledigital:
            probe=source/'tools/community/inspect_payroll_configuration.py'
            expression="import runpy; runpy.run_path("+repr(str(probe))+")["+repr('inspect')+"](env,"+repr(str(stage/'configuration.json'))+")"
            with (stage/'configuration-bootstrap.log').open('w') as stream:
                status=subprocess.run(offline_odoo(base+['shell']+opts+['--no-http','--logfile='+str(stage/'configuration.log')]),
                    input=expression,text=True,stdout=stream,stderr=subprocess.STDOUT)
            report_log=(stage/'configuration.log').read_text(errors='replace')
            assert status.returncode==0 and not re.search(r' (ERROR|CRITICAL) ',report_log),'Configuration inspector failed'
        if args.accelerated:
            checker=source/'tools/community/finance_frontier_contract.py'
            expression="import runpy,json; proof=runpy.run_path("+repr(str(checker))+")[\"verify\"](env,"+repr('community' if pure else 'cerro-copy')+",draft_grouping="+repr(args.custody_grouping)+");open("+repr(str(stage/'finance-frontier.json'))+",'w').write(json.dumps(proof,indent=2))"
            with (stage/'finance-bootstrap.log').open('w') as stream:
                status=subprocess.run(offline_odoo(base+['shell']+opts+['--no-http','--logfile='+str(stage/'finance.log')]),input=expression,text=True,stdout=stream,stderr=subprocess.STDOUT)
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
            identity_for_check=current
            if args.multifront:
                treasury_after=treasury_snapshot(sql,args.database);dump_json('treasury-after',treasury_after)
                treasury_proof,identity_for_check=verify_treasury(original,current,json.loads((stage/'treasury-before.json').read_text()),treasury_after,source)
                dump_json('treasury-metadata-proof',treasury_proof)
            if args.accelerated:dump_json('hr-metadata-proof',verify_hr_metadata(original,identity_for_check))
            for name,rows in original.items():
                if args.accelerated and name=='ir_model_fields':continue  # all rows verified above, with three exact message edits
                if rows and 'id' in rows[0]:
                    now={r['id']:r for r in identity_for_check[name]}
                    assert all(now.get(r['id'])==r for r in rows),(name,'Original metadata changed')
                else:assert all(row in identity_for_check[name] for row in rows),name
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
        dump_json('passed',{'mode':args.mode,'profile':args.profile,'accelerated':args.accelerated,'custody_grouping':args.custody_grouping,'database':args.database,'writes_to_source':False,'package_files':len(fp),
            'source_files_sha256':hashlib.sha256((stage/'source-files.json').read_bytes()).hexdigest(),
            'counts':counts,'pdf_binary_reports':2 if binary_book else 0,'own_book_installed':book_installed,'own_book_library_only':bool(own_book and pure and not full_book),'payroll_model_registered':bool(engine_models),'oca_revision':PIN,'official_community_revision':OFFICIAL_PIN if pure else None,'historical_conversion':False,'simpledigital_certified':False,
            'test_results':[l for l in text.splitlines() if 'tests.result' in l],
            'expected_test_count':expected,
            'api_test_count':api_test_count if pure else 0,'base_test_count':base_test_count if pure else 0,
            'reference_test_count':reference_test_count if not pure else 0,
            'dte_test_count':dte_test_count,'external_network_disabled':True,'loopback_http_only':True,
            'hr_test_count':HR_TEST_COUNT if args.accelerated else 0,
            'postgres_unix_socket':True,'offline_runner_sha256':hashlib.sha256((source/'tools/community/offline_process.py').read_bytes()).hexdigest(),
            'multifront':args.multifront,'focused_development_pass':args.focused_multifront,
            'numeric_input_engine':bool(pure and args.numeric_input_engine),
            'numeric_engine_derivation_sha256':hashlib.sha256((root/'oca-input-numeric-derivation.json').read_bytes()).hexdigest() if pure and args.numeric_input_engine else None,
            'stored_payslip_pdf_reports':stored_pdf_count,
            'identity_snapshot_tool_sha256':hashlib.sha256((source/'tools/community/validate_agriculture_core.py').read_bytes()).hexdigest(),
            'original_xmlid_noupdate_captured':bool(not pure and original.get('original_xmlids') and all('noupdate' in row for row in original['original_xmlids'])),
            'accelerated_tools_sha256':{name:hashlib.sha256((source/'tools/community'/name).read_bytes()).hexdigest() for name in ('accelerated_acceptance.py','hr_consumers_candidate.py','finance_frontier_contract.py','hr_consumer_metadata.py')} if args.accelerated else {},
            'validator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
        print('PAYROLL_API_OK '+args.mode,flush=True)


if __name__=='__main__':main()
