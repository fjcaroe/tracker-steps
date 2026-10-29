"""Verify exported private API evidence against this checkout, without database access."""
import argparse
import ast
import hashlib
import io
import tarfile
import json
import subprocess
from decimal import Decimal
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    repo=Path(__file__).resolve().parents[2]
    def read(mode,name):
        return json.loads((args.evidence/mode/(name+'.json')).read_text(encoding='utf-8'))
    packets=[read(mode,'source-files') for mode in ('community','cerro-reference')]
    assert packets[0]==packets[1], 'Different addon packets'
    # git archive applies export EOL filters too. Pin the Windows export used
    # for the accepted package instead of confusing export bytes with raw blobs.
    simpledigital=read('community','passed').get('profile') in ('simpledigital','previred','previred-simpledigital','book-consumers','book-install','book-history')
    paths=['step_payroll_contracts','step_payroll_oca_api','step_payroll_enterprise_reference',
           'tools/community/validate_payroll_api.py']
    if simpledigital:paths+=['step_simpledigital_oca_base','step_simpledigital_oca_security','tools/community/build_simpledigital_candidate.py','tools/community/simpledigital_runtime_source.json']
    accelerated=read('community','passed').get('accelerated',False)
    if accelerated:
        hr_modules=('step_hr_contract_lifecycle','step_hr_contract_lifecycle_simpledigital','step_payroll_engine_transition','steps_hr_payroll_correction')
        paths+=list(hr_modules)+['step_accounting_multicurrency_core','step_account_balance_analytic','step_bank_export_core',
            'step_account_treasury_batch','step_bank_security','step_l10n_cl_edi_core',
            'tools/community/accelerated_acceptance.py','tools/community/hr_consumers_candidate.py','tools/community/finance_frontier_contract.py']
    previred=read('community','passed').get('profile') in ('previred','previred-simpledigital','book-consumers','book-install','book-history')
    bridge=read('community','passed').get('profile') in ('previred-simpledigital','book-consumers','book-install','book-history')
    if previred:paths+=['step_hr_previred']
    if bridge:paths+=['step_hr_previred_simpledigital']
    if read('community','passed').get('profile') in ('book-consumers','book-install','book-history'):paths+=['step_hr_remuneration_book']
    if read('community','passed').get('profile') in ('book-install','book-history'):paths+=['tools/community/build_book_candidate.py']
    cleanups=sorted(args.evidence.glob('retention*/cleanup-result.json'),key=lambda p:p.parent.name)
    if cleanups:paths+=['tools/community/cleanup_payroll_rehearsals.py']
    group_proof=args.evidence/'group-preservation.json'
    if group_proof.exists():paths+=['tools/community/verify_payroll_group_preservation.py']
    configuration=args.evidence/'community/configuration.json'
    if configuration.exists():paths+=['tools/community/inspect_payroll_configuration.py']
    origins=args.evidence/'profile-origins.json'
    if origins.exists():paths+=['tools/community/audit_payroll_profile_sources.py']
    sys_reference=args.evidence/'sys-reference.json'
    if sys_reference.exists():paths+=['tools/community/audit_sys_payroll_reference.py']
    sys_provider=args.evidence/'sys-provider-source.json'
    if sys_provider.exists():paths+=['tools/community/audit_payroll_community.py']
    storage=args.evidence/'storage-proof.json'
    if storage.exists():paths+=['tools/community/prepare_payroll_storage.py']
    resize=args.evidence/'disk-resize-proof.json'
    if resize.exists():paths+=['tools/ops/resize_community_data_disk.py']
    collisions=args.evidence/'rule-collisions'
    if collisions.exists():paths+=['tools/community/probe_payroll_rule_collisions.py','tools/community/run_payroll_rule_probe.py']
    temporal=args.evidence/'temporal-basis.json'
    if temporal.exists():paths+=['tools/community/audit_sys_payroll_temporal_basis.py']
    document=args.evidence/'document/document-proof.json'
    if document.exists():paths+=['tools/community/export_sys_reference_document.py']
    comparison=args.evidence/'document-comparison.json'
    if comparison.exists():paths+=['tools/community/compare_sys_reference_document.py']
    basis=args.evidence/'basis-input.json'
    if basis.exists():paths+=['tools/community/audit_sys_monthly_basis.py','tools/community/probe_monthly_basis.py']
    ytd=args.evidence/'native-ytd/observations.json'
    if ytd.exists():paths+=['tools/community/probe_payroll_ytd.py']
    upgrade=args.evidence/'history-upgrade/passed.json'
    if upgrade.exists():paths+=['tools/community/validate_payroll_history_upgrade.py']
    exported=subprocess.check_output(['git','-C',str(repo),'-c','core.autocrlf=true',
        '-c','core.eol=crlf','archive','--format=tar','HEAD',*paths])
    with tarfile.open(fileobj=io.BytesIO(exported)) as archive:
        source={m.name:archive.extractfile(m).read() for m in archive.getmembers() if m.isfile()}
    for name,digest in packets[0].items():
        if simpledigital and name.startswith('l10n_cl_simpledigital_payroll/'):
            blob=(args.evidence/'provider'/name).read_bytes()
            assert hashlib.sha256(blob).hexdigest()==digest,name
            continue
        blob=source[name]
        if read('community','passed').get('profile') in ('book-install','book-history') and name=='step_hr_remuneration_book/__manifest__.py':
            blob=blob.replace(b'"hr_payroll"',b'"step_simpledigital_oca_security"')
        assert hashlib.sha256(blob).hexdigest()==digest, name
        assert (repo/name).read_bytes().replace(b'\r\n',b'\n')==source[name].replace(b'\r\n',b'\n'),name
    if read('community','passed').get('profile') in ('book-install','book-history'):
        proof=json.loads((args.evidence/'book-derivation.json').read_text(encoding='utf-8'))
        assert proof['transformation']=='real_simpledigital_prerequisite_only' and proof['license']=='LGPL-3'
        assert proof['builder_sha256']==hashlib.sha256(source['tools/community/build_book_candidate.py']).hexdigest()
        for name,digest in proof['source_files'].items():
            assert digest==hashlib.sha256(source['step_hr_remuneration_book/'+name]).hexdigest()
            assert proof['candidate_files'][name]==packets[0]['step_hr_remuneration_book/'+name]
        assert not proof['generic_canonical_dependency_retired'] and not proof['full_cerro_conversion']
    if simpledigital:
        derivation=json.loads((args.evidence/'provider-derivation.json').read_text(encoding='utf-8'))
        pin=json.loads(source['tools/community/simpledigital_runtime_source.json'].decode('utf-8-sig'))
        assert derivation['source_files']==pin['files'] and derivation['license']=='AGPL-3'
        assert derivation['builder_sha256']==hashlib.sha256(source['tools/community/build_simpledigital_candidate.py']).hexdigest()
    if accelerated:
        proof=read('community','hr-consumers-derivation')
        assert proof['community_candidate'] and not proof['identity_conversion_accepted']
        assert proof['builder_sha256']==hashlib.sha256(source['tools/community/hr_consumers_candidate.py']).hexdigest()
        # Reproduce each declared transformation from the exact Git packet.
        dependencies={'hr_payroll':'step_simpledigital_oca_security','hr_work_entry_contract_enterprise':'hr_work_entry_contract'}
        actual=read('community','consumer-source-files');native=read('cerro-reference','consumer-source-files')
        expected={}
        for module in hr_modules:
            for relative,hashes in proof['modules'][module]['files'].items():
                name=module+'/'+relative;blob=source[name]
                assert hashlib.sha256(blob).hexdigest()==hashes['source']==packets[0][name]==native[name]
                if relative=='__manifest__.py':
                    manifest=ast.literal_eval(blob.decode('utf-8-sig'))
                    manifest['depends']=list(dict.fromkeys(dependencies.get(d,d) for d in manifest['depends']))
                    blob=(repr(manifest)+'\n').encode()
                elif name.endswith(('.xml','.csv')):
                    text=blob.decode('utf-8-sig')
                    for old,new in proof['xmlid_map'].items():text=text.replace(old,new)
                    blob=text.encode()
                digest=hashlib.sha256(blob).hexdigest()
                assert actual[name]==hashes['candidate']==digest,name
                expected[name]=digest
        assert actual==expected and set(native)==set(expected)
    results={mode:read(mode,'passed') for mode in ('community','cerro-reference')}
    assert results['community']['counts']['enterprise']==0
    assert results['cerro-reference']['counts']['enterprise']==140
    if results['community'].get('profile')=='book-consumers':
        assert results['community']['own_book_library_only'] and not results['community']['own_book_installed']
        assert results['cerro-reference']['own_book_installed'] and not results['cerro-reference']['own_book_library_only']
    if results['community'].get('profile') in ('book-install','book-history'):
        assert all(r['own_book_installed'] and not r['own_book_library_only'] for r in results.values())
    assert all(not r['writes_to_source'] and not r['historical_conversion'] and not r['simpledigital_certified'] for r in results.values())
    assert len({r['source_files_sha256'] for r in results.values()})==1
    validator=source['tools/community/validate_payroll_api.py']
    assert all(r['validator_sha256']==hashlib.sha256(validator).hexdigest() for r in results.values())
    before=read('cerro-reference','business-before')
    for name in ('business-after-upgrade','business-after'):
        after=read('cerro-reference',name)
        assert before.keys()==after.keys()
        assert all((v['rows'],v['hash'])==(after[k]['rows'],after[k]['hash']) for k,v in before.items()),name
    original=read('cerro-reference','identity-before');current=read('cerro-reference','identity-after')
    for name,rows in original.items():
        if rows and 'id' in rows[0]:
            indexed={row['id']:row for row in current[name]}
            assert all(indexed.get(row['id'])==row for row in rows),name
        else:
            assert all(row in current[name] for row in rows),name
    assert read('cerro-reference','history-before')==read('cerro-reference','history-after')
    result={'results':results,'original_business_contracts_preserved':len(before),
        'original_identity_rows_preserved':{key:len(rows) for key,rows in original.items()},
        'exact_packet_matches_checkout':True,'full_cerro_conversion':False,
        'simpledigital_certified':False,'deadline_resolved':False}
    if accelerated:
        assert results['cerro-reference']['accelerated']
        assert results['community']['expected_test_count']==228 and results['cerro-reference']['expected_test_count']==199
        for report in results.values():
            assert all(report['accelerated_tools_sha256'][name]==hashlib.sha256(source['tools/community/'+name]).hexdigest()
                       for name in report['accelerated_tools_sha256'])
        bank_before=read('cerro-reference','bank-metadata-before');bank_after=read('cerro-reference','bank-metadata-after')
        import importlib.util
        spec=importlib.util.spec_from_file_location('finance_frontier_contract',repo/'tools/community/finance_frontier_contract.py')
        helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
        assert (repo/'tools/community/finance_frontier_contract.py').read_bytes().replace(b'\r\n',b'\n')==source['tools/community/finance_frontier_contract.py'].replace(b'\r\n',b'\n')
        assert helper.verify_metadata(bank_before,bank_after)==read('cerro-reference','bank-metadata-proof')
        for mode in ('community','cerro-reference'):
            finance=read(mode,'finance-frontier')
            assert len(finance['aliases'])==11 and finance['payment_formats_use_original_model'] and not finance['batch_conversion_certified']
        result['accelerated']={'hr_consumers_installed':list(hr_modules),'bank_aliases_preserved':11,
            'caf_authenticity_core_only':True,'full_dte_certified':False,'batch_conversion_certified':False}
    if all(report.get('pdf_binary_reports') for report in results.values()):
        result['pdf_binary_reports']={}
        for mode in ('community','cerro-reference'):
            directory=args.evidence/mode/'pdf-evidence'
            pdfs=json.loads((directory/'pdf-proof.json').read_text(encoding='utf-8'))
            assert len(pdfs)==2 and {row['report'] for row in pdfs}=={'consolidated_book','employee_sheets'}
            for row in pdfs:
                blob=(directory/(row['report']+'.pdf')).read_bytes()
                assert blob.startswith(b'%PDF-') and hashlib.sha256(blob).hexdigest()==row['sha256']
                assert row['normal_actor'] and row['single_audit'] and row['history_preserved'] and row['pages']>0
            result['pdf_binary_reports'][mode]=pdfs
    if sys_reference.exists():
        proof=json.loads(sys_reference.read_text(encoding='utf-8'))
        executed=(args.evidence/'reference-auditor.py').read_bytes()
        assert executed.replace(b'\r\n',b'\n')==source['tools/community/audit_sys_payroll_reference.py'].replace(b'\r\n',b'\n')
        assert proof['read_only'] and not proof['orm_reads'] and not proof['payroll_computed']
        assert not proof['financial_certified'] and not proof['identity_conversion'] and not proof['formula_bodies_exported']
        assert not proof['direct_employee_identifiers_exported'] and proof['private_payroll_amounts_exported']
        selected=proof['selected_case']
        assert selected and selected['state'] in ('done','paid') and set(selected['concepts'])=={'BASIC','GROSS','NET'}
        assert all(len({row['salary_rule_id'] for row in rows})==1 for rows in selected['concepts'].values())
        assert all(sum((Decimal(row['total']) for row in rows),Decimal(0))==Decimal(selected['stored_totals'][code]) for code,rows in selected['concepts'].items())
        if 'selection_helper_sha256' in proof:
            helper=(args.evidence/'selection-helper.py').read_bytes()
            assert hashlib.sha256(helper).hexdigest()==proof['selection_helper_sha256']
            assert helper.replace(b'\r\n',b'\n')==source['step_payroll_contracts/reference.py'].replace(b'\r\n',b'\n')
            assert proof['zero_cases_preserved']
            positive=all(Decimal(value)>0 for value in selected['stored_totals'].values())
            assert proof['selected_case_has_positive_essential_totals']==positive
            assert positive or proof['positive_closed_previous_month_cases']==0
        result['sys_reference']={'closed_slips':proof['closed_slips'],'unambiguous_complete_slips':proof['unambiguous_complete_slips'],
            'ambiguous_concepts':len(proof['ambiguous_concepts']),'incomplete_slips':len(proof['incomplete_slip_ids']),
            'selected_period':selected['date_to'][:7],'financial_certified':False,'source_read_only':True}
        if 'selection_helper_sha256' in proof:
            result['sys_reference'].update({key:proof[key] for key in ('positive_closed_previous_month_cases','selected_case_has_positive_essential_totals','zero_cases_preserved')})
    if sys_provider.exists():
        proof=json.loads(sys_provider.read_text(encoding='utf-8'))
        executed=(args.evidence/'sys-provider-inspector.py').read_bytes()
        assert executed.replace(b'\r\n',b'\n')==source['tools/community/audit_payroll_community.py'].replace(b'\r\n',b'\n')
        assert proof['read_only'] and not proof['formula_bodies_exported']
        provider=proof['module_source'];assert provider['manifest']['license']=='AGPL-3'
        inventory=json.loads((args.evidence/'inventory-current.json').read_text(encoding='utf-8'))
        same=provider['source_sha256']==inventory['modules']['l10n_cl_simpledigital_payroll']['source_sha256']
        assert same==proof['same_as_cerro_original']
        result['sys_provider']={'files':provider['files'],'license':provider['manifest']['license'],'same_as_cerro_original':same}
    if storage.exists():
        proof=json.loads(storage.read_text(encoding='utf-8'))
        executed=(args.evidence/'storage-preparer.py').read_bytes()
        assert hashlib.sha256(executed).hexdigest()==proof['tool_sha256']
        assert executed.replace(b'\r\n',b'\n')==source['tools/community/prepare_payroll_storage.py'].replace(b'\r\n',b'\n')
        assert not any(proof[key] for key in ('existing_databases_moved','server_configuration_changed','credentials_changed'))
        actual=json.loads((args.evidence/'database-storage.json').read_text(encoding='utf-8'))
        for mode in ('community','cerro-reference'):
            key='community' if mode=='community' else 'cerro'
            target=proof['tablespaces'][key]
            planned=read(mode,'storage-preflight')['validation_tablespace']
            assert planned['name']==target['name'] and planned['location']==target['location']
            assert actual[mode]['database']==results[mode]['database'] and actual[mode]['tablespace']==target['name']
            assert actual[mode]['foreign_public_relations']==0
        result['private_storage']={'existing_databases_moved':False,'server_configuration_changed':False,'credentials_changed':False,'new_databases_verified':True}
    if resize.exists():
        proof=json.loads(resize.read_text(encoding='utf-8'))
        executed=(args.evidence/'disk-resizer.py').read_bytes()
        assert hashlib.sha256(executed).hexdigest()==proof['tool_sha256']
        assert executed.replace(b'\r\n',b'\n')==source['tools/ops/resize_community_data_disk.py'].replace(b'\r\n',b'\n')
        assert proof['completed'] and proof['postgres_ready_after'] and proof['cloud_size_gib']==150
        assert not any(proof[key] for key in ('database_dml','service_restart','credentials_changed'))
        assert set(proof['backups'])=={'SyS','CERRO_EL_PLOMO'}
        assert all(row['fully_decoded'] and len(row['sha256'])==64 for row in proof['backups'].values())
        assert proof['snapshot']['status']=='READY' and int(proof['snapshot']['diskSizeGb'])==100
        assert proof['filesystem_bytes_after']>140*1024**3 and proof['postgres_available_bytes_after']>=5*1024**3
        result['approved_capacity_change']={'target_gib':150,'backups_decoded':2,'snapshot_ready':True,'database_dml':False,'service_restart':False}
    versions=args.evidence/'contracts-version-proof.json'
    if versions.exists():
        proof=json.loads(versions.read_text(encoding='utf-8'))
        assert proof['read_only'] and set(proof['versions'])=={'community','cerro-reference'}
        expected_version=ast.literal_eval(source['step_payroll_contracts/__manifest__.py'].decode('utf-8-sig'))['version']
        assert set(proof['versions'].values())=={expected_version}
        result['contracts_versions']=proof['versions']
    api_version=args.evidence/'api-version-proof.json'
    if api_version.exists():
        proof=json.loads(api_version.read_text())
        assert proof['read_only'] and not proof['reference_api_installed']
        assert proof['community_api']==ast.literal_eval(source['step_payroll_oca_api/__manifest__.py'].decode('utf-8-sig'))['version']
        result['community_api_version']=proof['community_api']
    if document.exists():
        proof=json.loads(document.read_text())
        executed=(document.parent/'exporter.py').read_bytes();pdf=(document.parent/'reference.pdf').read_bytes()
        assert hashlib.sha256(executed).hexdigest()==proof['exporter_sha256']
        assert executed.replace(b'\r\n',b'\n')==source['tools/community/export_sys_reference_document.py'].replace(b'\r\n',b'\n')
        assert proof['read_only'] and proof['contains_private_identity_and_payroll_data']
        assert not any(proof[key] for key in ('orm_reads','report_generated','payroll_computed','financial_certified','historical_wage_proven'))
        assert proof['capsule_sha256']==hashlib.sha256(sys_reference.read_bytes()).hexdigest()
        assert pdf.startswith(b'%PDF-') and hashlib.sha256(pdf).hexdigest()==proof['pdf_sha256']
        assert hashlib.sha1(pdf).hexdigest()==proof['attachment']['checksum'] and len(pdf)==proof['attachment']['file_size']
        result['existing_reference_document']={'source_checksum_verified':True,'report_generated':False,'financial_certified':False,'historical_wage_proven':False}
    if comparison.exists():
        proof=json.loads(comparison.read_text())
        executed=(args.evidence/'document-comparator.py').read_bytes()
        assert proof['comparator_sha256']==hashlib.sha256(executed).hexdigest()
        assert executed.replace(b'\r\n',b'\n')==source['tools/community/compare_sys_reference_document.py'].replace(b'\r\n',b'\n')
        assert proof['capsule_sha256']==hashlib.sha256(sys_reference.read_bytes()).hexdigest()
        assert proof['pdf_sha256']==hashlib.sha256((document.parent/'reference.pdf').read_bytes()).hexdigest()
        assert proof['read_only'] and proof['documentary_wage_observed'] and proof['private_payroll_amounts_exported']
        assert not any(proof[key] for key in ('report_generated','payroll_computed','financial_certified','master_timeline_certified',
            'direct_employee_identifiers_exported','formula_bodies_exported'))
        assert Decimal(proof['printed_contract_wage']).is_finite() and Decimal(proof['printed_contract_wage'])>0
        assert proof['basic_matches_stored'] and proof['net_matches_stored']
        result['documentary_reference']={key:proof[key] for key in ('documentary_wage_observed','basic_matches_stored','net_matches_stored',
            'taxable_matches_stored_gross','total_earnings_matches_stored_gross','master_timeline_certified','financial_certified')}
    if basis.exists():
        inputs=json.loads(basis.read_text())
        auditor=(args.evidence/'basis-auditor.py').read_bytes();helper=(args.evidence/'basis-helper.py').read_bytes();probe=(args.evidence/'basis-probe.py').read_bytes()
        for name,blob in [('tools/community/audit_sys_monthly_basis.py',auditor),('step_payroll_contracts/basis.py',helper),('tools/community/probe_monthly_basis.py',probe)]:
            assert blob.replace(b'\r\n',b'\n')==source[name].replace(b'\r\n',b'\n')
        assert inputs['auditor_sha256']==hashlib.sha256(auditor).hexdigest() and inputs['basis_helper_sha256']==hashlib.sha256(helper).hexdigest()
        assert inputs['formula_sha256']==hashlib.sha256(inputs['formula'].encode()).hexdigest()
        assert inputs['capsule_sha256']==hashlib.sha256(sys_reference.read_bytes()).hexdigest()
        documentary=json.loads(comparison.read_text());reference=json.loads(sys_reference.read_text())
        assert inputs['pdf_sha256']==documentary['pdf_sha256']
        assert Decimal(inputs['printed_contract_wage'])==Decimal(documentary['printed_contract_wage'])
        assert Decimal(inputs['expected_basic'])==Decimal(reference['selected_case']['stored_totals']['BASIC'])
        original_line=reference['selected_case']['concepts']['BASIC'][0]
        components=inputs['expected_components']
        assert inputs['components_read_only_sql'] and components['id']==original_line['id']
        assert components['slip_id']==reference['selected_case']['id'] and components['salary_rule_id']==original_line['salary_rule_id']
        assert components['code']=='BASIC' and components['write_date']==original_line['write_date']
        assert all(components[key] is not None and Decimal(components[key]).is_finite() for key in ('amount','quantity','rate','total'))
        assert Decimal(components['total'])==Decimal(inputs['expected_basic'])
        original_id=reference['selected_case']['concepts']['BASIC'][0]['salary_rule_id']
        assert inputs['formula_sha256']==next(row['body_sha256'] for row in reference['essential_rule_origins'] if row['id']==original_id)
        assert inputs['read_only_source'] and inputs['contains_private_formula_and_payroll_data']
        assert not any(inputs[key] for key in ('orm_reads','source_payroll_computed','enterprise_source_files_copied','financial_certified','master_timeline_certified'))
        observations={mode:read(mode,'monthly-basis') for mode in ('community','cerro-reference')}
        for proof in observations.values():
            assert proof['probe_sha256']==hashlib.sha256(probe).hexdigest()
            assert proof['normal_actor'] and proof['real_engine'] and proof['new_fixture_only'] and proof['fixtures_rolled_back']
            assert proof['transaction_case'] and proof['rollback_verified'] and proof['fixture_master_counts']=={'companies':0,'users':0}
            assert proof['basic_matches_original_snapshot']
            assert proof['stored_component_reader'] and proof['component_matches']==dict.fromkeys(('amount','quantity','rate','total'),True)
            assert not any(proof[key] for key in ('source_payroll_computed','source_written','financial_certified','master_timeline_certified','full_payroll_replay','identity_conversion'))
            assert all(proof[key]==inputs[key] for key in ('capsule_sha256','pdf_sha256','formula_sha256'))
            assert all(row['source_id'] and row['target_id'] and row['code'] for row in proof['worked_day_master_mapping'])
        result['monthly_basic_reference']={'engines':2,'basic_matches_original_snapshot':True,'real_engine':True,
            'fixtures_rolled_back':True,'rollback_verified':True,'transaction_case':True,
            'full_payroll_replay':False,'financial_certified':False,'identity_conversion':False,
            'component_matches':dict.fromkeys(('amount','quantity','rate','total'),True),
            'basis':inputs['basis'],'rule_write_date_precedes_period':inputs['rule_write_date_precedes_period']}
    if collisions.exists():
        probe=(collisions/'probe.py').read_bytes();runner=(collisions/'runner.py').read_bytes()
        for name,blob in [('probe_payroll_rule_collisions.py',probe),('run_payroll_rule_probe.py',runner)]:
            assert blob.replace(b'\r\n',b'\n')==source['tools/community/'+name].replace(b'\r\n',b'\n')
        observations={}
        for mode in ('community','cerro-reference'):
            proof=json.loads((collisions/mode/'observations.json').read_text())
            assert proof['probe_sha256']==hashlib.sha256(probe).hexdigest()
            assert proof['runner_sha256']==hashlib.sha256(runner).hexdigest()
            assert proof['normal_actor'] and proof['synthetic_only'] and proof['fixtures_rolled_back']
            assert not proof['writes_to_source'] and not proof['financial_certified']
            assert proof['baseline_source_files_sha256']=='3d854cda1fff74e8b3db8c685be9d8da45606260cdda1fd075ae70d800732773'
            observations[mode]=proof['observations']
        assert observations['community']==observations['cerro-reference']
        assert set(observations['community'])=={'same_sequence_distinct_categories','reverse_sequence','same_category','second_zero'}
        result['rule_collision_observations']={'cases':4,'engines_match':True,'synthetic_only':True,'financial_certified':False}
    if temporal.exists():
        proof=json.loads(temporal.read_text())
        executed=(args.evidence/'temporal-auditor.py').read_bytes()
        assert proof['auditor_sha256']==hashlib.sha256(executed).hexdigest()
        assert executed.replace(b'\r\n',b'\n')==source['tools/community/audit_sys_payroll_temporal_basis.py'].replace(b'\r\n',b'\n')
        assert proof['capsule_sha256']==hashlib.sha256(sys_reference.read_bytes()).hexdigest()
        assert proof['read_only'] and not any(proof[key] for key in ('orm_reads','payroll_computed','financial_certified',
            'historical_wage_proven','private_payroll_amounts_exported','direct_employee_identifiers_exported',
            'formula_bodies_exported','absence_of_tracking_proves_no_change','history_relation_is_an_immutable_snapshot'))
        result['temporal_basis']={key:proof[key] for key in ('selected_period','current_contract_modified_after_period',
            'contract_history_relation_kind','contract_history_reads_current_contract_wage','tracking_event_counts','historical_wage_proven')}
    ui=args.evidence/'community'/'configuration-probe.json'
    if ui.exists():
        probe=json.loads(ui.read_text(encoding='utf-8'))
        assert probe['menu_visible'] and probe['configuration_saved_with_normal_permissions']
        assert not probe['actor_sudo'] and probe['fixtures_rolled_back']
        result['configuration_probe']=probe
    schema=args.evidence/'schema-delta.json'
    if schema.exists():
        mapping=json.loads(schema.read_text(encoding='utf-8'))
        assert mapping['read_only'] and not mapping['identity_migration_accepted']
        assert not mapping['simpledigital_certified'] and mapping['vendor']['simpledigital_installed']==simpledigital
        result['schema_delta_counts']=mapping['counts']
        if simpledigital:
            provider=[{'model':row['model'],'field':row['field'],'differences':row['differences']} for row in mapping['differences'] if any(x.startswith('l10n_cl_simpledigital_payroll.') for x in row['source_identity']['xmlids'])]
            assert not provider,'Supplier fields differ from source contract'
            result['provider_field_differences']=provider
    reproduction=args.evidence/'reproduction.json'
    if reproduction.exists():
        proof=json.loads(reproduction.read_text(encoding='utf-8'))
        assert proof['same_runtime_bytes']
        assert proof['builder_sha256']==hashlib.sha256(source['tools/community/build_simpledigital_candidate.py']).hexdigest()
        result['provider_reproduction']=proof
    if upgrade.exists():
        proof=json.loads(upgrade.read_text(encoding='utf-8'))
        executed=(args.evidence/'history-upgrade/probe.py').read_bytes()
        assert hashlib.sha256(executed).hexdigest()==proof['probe_sha256']
        assert executed.replace(b'\r\n',b'\n')==source['tools/community/validate_payroll_history_upgrade.py'].replace(b'\r\n',b'\n')
        assert all(proof[key] for key in ('actual_upgrade','rejected_missing_snapshots','real_engine','normal_actor','original_payroll_rows_preserved','historical_values_preserved','closure_marked_by_upgrade','synthetic_fixture_only'))
        assert not proof['writes_to_source'] and not proof['full_cerro_conversion']
        seed=json.loads((args.evidence/'history-upgrade/seed.json').read_text(encoding='utf-8'))
        proof['ledger_row_counts']={name:len(seed['original_rows'][name]) for name in ('account_move','account_move_line')}
        assert all(proof['ledger_row_counts'].values())
        result['history_upgrade']=proof
    if configuration.exists():
        executed=(args.evidence/'configuration-inspector.py').read_bytes()
        assert executed.replace(b'\r\n',b'\n')==source['tools/community/inspect_payroll_configuration.py'].replace(b'\r\n',b'\n')
        reports={}
        for mode in ('community','cerro-reference'):
            value=read(mode,'configuration')
            assert value['normal_actor'] and value['read_only_configuration'] and value['fixtures_rolled_back']
            assert not value['writes_to_source'] and not value['financial_certified']
            chile=next(row for row in value['reports'] if row['structure_id']==value['chile_structure_id'])
            assert not chile['financial_certified']
            if mode=='cerro-reference':assert value['chile_rule_alias_ids']==chile['essential_ids']
            reports[mode]={'normal_actor':True,'total_rules':sum(row['rule_count'] for row in value['reports']),
                'chile_rules':chile['rule_count'],'chile_errors':chile['errors'],
                'original_essential_ids':chile['essential_ids'],'rule_alias_ids':value['chile_rule_alias_ids']}
        result['configuration']=reports
    if origins.exists():
        value=json.loads(origins.read_text(encoding='utf-8'))
        assert value['read_only'] and not value['formula_bodies_exported'] and not value['employee_data_exported'] and not value['financial_certified']
        executed=(args.evidence/'profile-auditor.py').read_bytes()
        assert executed.replace(b'\r\n',b'\n')==source['tools/community/audit_payroll_profile_sources.py'].replace(b'\r\n',b'\n')
        result['profile_origins']={name:profile['active_essential_ids'] for name,profile in value['profiles'].items()}
        if all('historical_net_rule_counts' in profile for profile in value['profiles'].values()):
            result['profile_net_history']={name:profile['historical_net_rule_counts'] for name,profile in value['profiles'].items()}
            assert all(row['line_count']>0 and row['salary_rule_id'] for rows in result['profile_net_history'].values() for row in rows)
    if ytd.exists():
        proof=json.loads(ytd.read_text(encoding='utf-8'))
        executed=(args.evidence/'native-ytd/probe.py').read_bytes()
        assert executed.replace(b'\r\n',b'\n')==source['tools/community/probe_payroll_ytd.py'].replace(b'\r\n',b'\n')
        assert proof['normal_actor'] and proof['synthetic_only'] and proof['fixtures_rolled_back'] and not proof['writes_to_source']
        assert proof['observations']['current']['ytd']==80 and proof['observations']['draft']['ytd']==30
        assert proof['extra']['overlapping']==95 and proof['extra']['same_period']==104
        result['native_ytd_observations']={'synthetic_only':True,'normal_actor':True,
            'fixtures_rolled_back':True,'financial_certified':False,'observations':proof['observations'],'extra':proof['extra']}
    if group_proof.exists():
        proof=json.loads(group_proof.read_text(encoding='utf-8'))
        executed=(args.evidence/'group-verifier.py').read_bytes()
        assert proof['verifier_sha256']==hashlib.sha256(executed).hexdigest()
        assert executed.replace(b'\r\n',b'\n')==source['tools/community/verify_payroll_group_preservation.py'].replace(b'\r\n',b'\n')
        assert proof['read_only'] and not proof['writes_to_source']
        assert all(row['identical'] and row['original_rows']==row['current_rows'] and row['original_sha256']==row['current_sha256'] for row in proof['bindings'].values())
        result['original_group_bindings_preserved']=proof
    cleanup_plans={}
    retained=set()
    for cleanup in cleanups:
        proof=json.loads(cleanup.read_text(encoding='utf-8'))
        executed=(cleanup.parent/'cleanup.py').read_bytes()
        plan_path=cleanup.parent/'cleanup-plan-resume.json'
        plan=json.loads(plan_path.read_text(encoding='utf-8'))
        assert proof['tool_sha256']==hashlib.sha256(executed).hexdigest()
        assert proof['plan_sha256']==hashlib.sha256(plan_path.read_bytes()).hexdigest()
        assert executed.replace(b'\r\n',b'\n')==source['tools/community/cleanup_payroll_rehearsals.py'].replace(b'\r\n',b'\n')
        assert proof['apply'] and proof['read_only_production'] and not proof.get('failure')
        assert {row['name'] for row in proof['databases']}==set(plan['delete_databases'])
        assert not set(plan['keep_databases'])&set(plan['delete_databases'])
        assert {row['path'] for row in proof['retained_backups']}==set(plan['keep_backups'])
        assert all(row['fully_decoded'] for row in proof['retained_backups'])
        retained.update(row['path'] for row in proof['retained_backups'])
        cleanup_plans[cleanup.parent.name]={'retired_databases':len(proof['databases'])+len(plan.get('already_retired_databases',[])),
            'retired_backups':len(proof['backups']),'retained_decoded_backups':len(proof['retained_backups']),
            'postgres_available_bytes_after':proof['postgres_available_bytes_after']}
    if cleanup_plans:
        result['retention_cleanup_plans']=cleanup_plans
        result['retention_cleanup']={
            'retired_databases':sum(value['retired_databases'] for value in cleanup_plans.values()),
            'retired_backups':sum(value['retired_backups'] for value in cleanup_plans.values()),
            'retained_decoded_backups':len(retained)}
        if len(cleanup_plans)==1:
            result['retention_cleanup']['postgres_available_bytes_after']=next(iter(cleanup_plans.values()))['postgres_available_bytes_after']
    standalone=args.evidence/'core-standalone/passed.json'
    if standalone.exists():
        proof=json.loads(standalone.read_text(encoding='utf-8'))
        packet=json.loads((args.evidence/'core-standalone/source-files.json').read_text(encoding='utf-8'))
        assert proof['profile']=='previred-standalone' and proof['counts']['enterprise']==0 and not proof['payroll_model_registered']
        assert not proof['writes_to_source'] and not proof['historical_conversion']
        assert proof['validator_sha256']==hashlib.sha256(validator).hexdigest()
        assert packet and all(packets[0].get(name)==value for name,value in packet.items())
        result['previred_standalone']=proof
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
