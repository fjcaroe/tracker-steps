"""Verify exported private API evidence against this checkout, without database access."""
import argparse
import ast
import hashlib
import io
import tarfile
import json
import subprocess
import sys
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
    custody_grouping=read('community','passed').get('custody_grouping',False)
    assert custody_grouping==read('cerro-reference','passed').get('custody_grouping',False)
    if custody_grouping:
        paths+=['step_batch_payment_grouping','step_batch_payment_core','step_l10n_cl_caf_custody_core',
                'step_l10n_cl_caf_storage','step_l10n_cl_caf_native_reference']
    if accelerated:
        hr_modules=('step_hr_contract_lifecycle','step_hr_contract_lifecycle_simpledigital','step_payroll_engine_transition','steps_hr_payroll_correction')
        paths+=list(hr_modules)+['step_accounting_multicurrency_core','step_account_balance_analytic','step_bank_export_core',
            'step_account_treasury_batch','step_bank_security','step_l10n_cl_edi_core','step_accounting_multicurrency',
            'tools/community/accelerated_acceptance.py','tools/community/hr_consumers_candidate.py','tools/community/finance_frontier_contract.py','tools/community/hr_consumer_metadata.py']
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
    relation_storage=args.evidence/'sys-storage/passed.json'
    if relation_storage.exists():paths+=['tools/community/validate_payroll_relation_storage.py']
    products=args.evidence/'products-inventory.json'
    if products.exists():paths+=['tools/community/audit_product_frontier.py']
    rule_source=args.evidence/'rule-source-proof.json'
    if rule_source.exists():paths+=['tools/community/hr_rule_source_audit.py']
    registry=args.evidence/'adoption-registry'
    if registry.exists():paths+=['tools/community/'+name for name in (
        'validate_adoption_registry.py','batch_registry_contract.py','caf_registry_contract.py','validate_payroll_relation_storage.py')]
    capsule=args.evidence/'configuration-capsule.json'
    if capsule.exists():paths+=['tools/community/export_payroll_configuration.py','tools/community/hr_configuration_scope_audit.py']
    stored_pdf=args.evidence/'pdf-reviewed/offline-pdf-proof.json'
    if stored_pdf.exists():paths+=['tools/community/verify_stored_payslip_pdf.py']
    config_storage=args.evidence/'configuration-storage/passed.json'
    if config_storage.exists():paths+=['tools/community/prepare_payroll_configuration_storage.py']
    adoption_preflight=args.evidence/'configuration-preflight/after.json'
    if adoption_preflight.exists():paths+=['tools/community/payroll_configuration_adoption_preflight.py']
    security_admission=args.evidence/'configuration-preflight/security-admission.json'
    if security_admission.exists():paths+=['tools/community/payroll_original_security_admission.py']
    identity_snapshotter=args.evidence/'identity-snapshotter.py'
    if identity_snapshotter.exists():paths+=['tools/community/validate_agriculture_core.py']
    property_upgrade=args.evidence/'properties-upgrade/passed.json'
    if property_upgrade.exists():paths+=['tools/community/validate_payroll_properties_upgrade.py']
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
    if accelerated:
        sys.path.insert(0,str(repo/'tools/community'))
        from hr_consumer_metadata import verify as hr_verify
        audit=hr_verify(original,current)
        audit['source']['sha256']=hashlib.sha256(source[audit['source']['path']]).hexdigest()
        assert audit==read('cerro-reference','hr-metadata-proof')
    for name,rows in original.items():
        if accelerated and name=='ir_model_fields':continue  # all original rows checked by the exact source-message policy
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
    if identity_snapshotter.exists():
        executed=identity_snapshotter.read_bytes()
        assert executed.replace(b'\r\n',b'\n')==source['tools/community/validate_agriculture_core.py'].replace(b'\r\n',b'\n')
        assert all(report['identity_snapshot_tool_sha256']==hashlib.sha256(executed).hexdigest() for report in results.values())
        assert results['cerro-reference']['original_xmlid_noupdate_captured']
        assert all('noupdate' in row for row in original['original_xmlids'])
        result['original_xmlid_noupdate_preserved']=True
    if property_upgrade.exists():
        import importlib.util
        folder=property_upgrade.parent
        proof=json.loads(property_upgrade.read_text())
        executed=(folder/'upgrade-probe.py').read_bytes()
        assert proof['tool_sha256']==hashlib.sha256(executed).hexdigest()
        assert executed.replace(b'\r\n',b'\n')==source['tools/community/validate_payroll_properties_upgrade.py'].replace(b'\r\n',b'\n')
        spec=importlib.util.spec_from_file_location('property_upgrade',repo/'tools/community/validate_payroll_properties_upgrade.py')
        helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
        seed=json.loads((folder/'seed.json').read_text())
        after_rows=json.loads((folder/'rows-after.json').read_text())
        check=helper.verify_rows(seed['raw_rows'],after_rows)
        assert all(proof[key]==value for key,value in check.items())
        assert all(proof[key] for key in ('actual_upgrade','normal_actor','real_oca_engine','historical_read_unchanged',
            'synthetic_fixture_only','synthetic_paid_marker','current_wage_changed_after_closure',
            'source_unchanged','source_filestore_unchanged','backup_decoded'))
        assert not any(proof[key] for key in ('closed_payroll_recomputed','payment_workflow_certified','customer_payroll_certified',
            'engine_conversion','writes_to_source','module_states_rewritten','full_community_conversion'))
        original_source=json.loads((folder/'source-before.json').read_text())
        assert original_source==json.loads((folder/'source-after.json').read_text())
        assert helper.digest(original_source)==proof['source_snapshot_sha256']
        baseline=json.loads((folder/'source-acceptance.json').read_text())
        assert hashlib.sha256((folder/'source-acceptance.json').read_bytes()).hexdigest()==proof['source_acceptance_sha256']
        assert baseline['database']==proof['source_database'] and baseline['counts']['enterprise']==0
        assert hashlib.sha256((folder/'source-packet.json').read_bytes()).hexdigest()==baseline['source_files_sha256']
        package=json.loads((folder/'package-files.json').read_text())
        assert helper.digest(package)==proof['package_files_sha256']
        for module,versions in helper.VERSIONS.items():
            assert proof['original_versions'][module]==versions[0] and proof['target_versions'][module]==versions[1]
            manifest=ast.literal_eval(source[module+'/__manifest__.py'].decode('utf-8-sig'))
            assert manifest['version']==versions[1]
            assert all(packets[0].get(module+'/'+name)==digest for name,digest in package[module]['candidate'].items())
        result['property_upgrade']={key:proof[key] for key in ('original_versions','target_versions','raw_rows_preserved',
            'model_ids_preserved','field_ids_preserved','historical_read_unchanged','source_unchanged',
            'synthetic_paid_marker','payment_workflow_certified','customer_payroll_certified','full_community_conversion')}
    if results['community'].get('stored_payslip_pdf_reports'):
        assert results['community']['stored_payslip_pdf_reports']==2
        directory=args.evidence/'community/payslip-pdf-evidence'
        proofs=list(directory.glob('proof-*.json'));assert len(proofs)==1
        records=json.loads(proofs[0].read_text(encoding='utf-8'))
        assert len(records)==2 and {(r['archived_structure'],r['basic_hidden']) for r in records}=={(False,False),(True,True)}
        for row in records:
            assert Path(row['file']).name==row['file']
            blob=(directory/row['file']).read_bytes()
            assert blob.startswith(b'%PDF-') and hashlib.sha256(blob).hexdigest()==row['sha256']
            assert row['normal_employee'] and row['stored_history_unchanged'] and not row['missing_assets'] and row['pages']>0
        assert stored_pdf.exists(),'Actual PDF text, row geometry and rendered-page review are required'
        offline=json.loads(stored_pdf.read_text(encoding='utf-8'))
        assert offline['input_proof_sha256']==hashlib.sha256(proofs[0].read_bytes()).hexdigest()
        executed=(stored_pdf.parent/'verifier.py').read_bytes()
        assert hashlib.sha256(executed).hexdigest()==offline['tool_sha256']
        assert executed.replace(b'\r\n',b'\n')==source['tools/community/verify_stored_payslip_pdf.py'].replace(b'\r\n',b'\n')
        assert offline['all_pages_rendered'] and not any(offline[key] for key in (
            'server_modified','substitute_pdf_generated','original_action_462_adopted','financial_payroll_certified'))
        reviewed=json.loads((stored_pdf.parent/'visual-review.json').read_text(encoding='utf-8'))
        assert reviewed['all_pages_inspected'] and reviewed['readable_without_clipping'] and reviewed['null_zero_negative_visibility_verified']
        assert reviewed['offline_proof_sha256']==hashlib.sha256(stored_pdf.read_bytes()).hexdigest()
        page_hashes={}
        for row in offline['pdfs']:
            original_pdf=next(r for r in records if r['file']==Path(row['pdf']).name)
            assert row['pdf_sha256']==original_pdf['sha256'] and len(row['pages'])==original_pdf['pages']
            assert all(row[key] for key in ('actual_pdf_labels_references_verified','zero_negative_net_values_verified',
                'source_history_unchanged_as_tested','null_row_verified_blank','signature_block_on_single_page'))
            assert not row['classification_history_certified']
            for page in row['pages']:
                assert Path(page['file']).name==page['file']
                digest=hashlib.sha256((stored_pdf.parent/page['file']).read_bytes()).hexdigest()
                assert digest==page['sha256'];page_hashes[page['file']]=digest
        assert reviewed['pages']==page_hashes
        result['stored_payslip_pdf']={'actual_pdfs':2,'rendered_pages_reviewed':len(page_hashes),
            'normal_employee':True,'stored_history_unchanged':True,'null_zero_negative_preserved':True,
            'original_action_462_adopted':False,'financial_payroll_certified':False}
    if config_storage.exists():
        folder=config_storage.parent
        proof=json.loads(config_storage.read_text(encoding='utf-8'))
        executed=(folder/'preparer.py').read_bytes()
        assert proof['tool_sha256']==hashlib.sha256(executed).hexdigest()
        assert executed.replace(b'\r\n',b'\n')==source['tools/community/prepare_payroll_configuration_storage.py'].replace(b'\r\n',b'\n')
        before_storage=json.loads((folder/'original-before.json').read_text())
        assert before_storage==json.loads((folder/'original-after.json').read_text())
        assert len(before_storage)==proof['original_contracts_preserved']
        assert proof['memberships']==71 and proof['company_or_parent_values_assigned']==0
        assert json.loads((folder/'relations.json').read_text())['sha256']==proof['sha256']
        assert all(proof[key] for key in ('backup_decoded','idempotence_verified','original_metadata_preserved'))
        assert not any(proof[key] for key in ('orm_loaded','engine_converted','financial_certified','writes_to_source','paid_payroll_recomputed'))
        prior_contract=json.loads((folder/'community-contract.json').read_text())
        current_contract=json.loads((folder/'community-current-contract.json').read_text())
        assert current_contract['versions']['step_payroll_oca_api']==ast.literal_eval(source['step_payroll_oca_api/__manifest__.py'].decode('utf-8-sig'))['version']
        assert current_contract['read_only'] and not current_contract['orm_loaded']
        assert all(prior_contract[key]==current_contract[key] for key in ('fields','relation'))
        result['configuration_storage']={key:proof[key] for key in ('database','memberships','original_contracts_preserved',
            'backup_decoded','backup_sha256','idempotence_verified','engine_converted','financial_certified')}
    if capsule.exists():
        sealed=json.loads(capsule.read_text(encoding='utf-8'))
        executed=(args.evidence/'configuration-exporter.py').read_bytes()
        assert sealed['tool_sha256']==hashlib.sha256(executed).hexdigest()
        assert executed.replace(b'\r\n',b'\n')==source['tools/community/export_payroll_configuration.py'].replace(b'\r\n',b'\n')
        assert sealed['read_only'] and not any(sealed[key] for key in (
            'orm_loaded','rules_evaluated','historical_payroll_read','engine_converted','financial_certified','import_authorized_by_capsule'))
        expected_configuration={'hr_payroll_structure':4,'hr_payroll_structure_type':5,
            'hr_payslip_input_type':6,'hr_salary_rule':71,'hr_salary_rule_category':34,
            'hr_payroll_structure_hr_payslip_input_type_rel':0}
        assert {table:report['row_count'] for table,report in sealed['tables'].items()}==expected_configuration
        for report in sealed['tables'].values():
            assert report['row_count']==len(report['rows_json'])
            assert report['rows_sha256']==hashlib.sha256('\n'.join(report['rows_json']).encode()).hexdigest()
        assert len(sealed['xmlids'])==91 and not sealed['unresolved_company_properties']
        journals=sealed['external_references']['hr_payroll_structure.journal_id']
        assert journals['company_dependent'] and journals['company_ids']==[1,2,3,4]
        assert journals['ids']==[8,16,24,32] and len(journals['original_values'])==12
        result['original_configuration_capsule']={'sha256':hashlib.sha256(capsule.read_bytes()).hexdigest(),
            'configuration_rows':expected_configuration,'xmlids':91,'all_company_properties_preserved':True,
            'adopted_on_oca':False,'financial_certified':False}
    if adoption_preflight.exists():
        import importlib.util
        spec=importlib.util.spec_from_file_location('configuration_preflight',repo/'tools/community/payroll_configuration_adoption_preflight.py')
        helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
        folder=adoption_preflight.parent
        executed=(folder/'auditor.py').read_bytes()
        assert executed.replace(b'\r\n',b'\n')==source['tools/community/payroll_configuration_adoption_preflight.py'].replace(b'\r\n',b'\n')
        prior=json.loads((folder/'before.json').read_text())
        current=json.loads(adoption_preflight.read_text())
        for report in (prior,current):
            assert report['tool_sha256']==hashlib.sha256(executed).hexdigest()
            assert report['capsule_sha256']==hashlib.sha256(capsule.read_bytes()).hexdigest()
            assert report['target_database']==results['community']['database']
            assert report['assessment']==helper.assess(sealed,report['source_metadata'],report['target_metadata'],
                report['source_external_metadata'],report['target_external_metadata'])
            assessment=report['assessment']
            assert assessment['source_capsule_matches_live_configuration'] and assessment['source_capsule_field_metadata_matches']
            assert assessment['target_has_zero_enterprise'] and assessment['reference_target_only']
            assert not any(assessment[key] for key in ('adoption_ready','import_authorized','permissions_expanded',
                'orm_loaded','rules_evaluated','salary_formulas_exposed','historical_payroll_read','record_rule_equivalence_certified'))
        preflight_comparison=helper.compare_reports(prior,current)
        assert current['read_only_comparison']==preflight_comparison and preflight_comparison['read_only_evidence_unchanged']
        closed={('hr.payroll.structure',name) for name in ('active','hide_basic_on_pdf','journal_id','payslip_name','report_id')}
        closed|={('hr.payroll.structure.type',name) for name in ('default_schedule_pay','default_work_entry_type_id','sequence','wage_type')}
        closed|={('hr.salary.rule',name) for name in ('amount_other_input_id','condition_other_input_id','partner_id','not_computed_in_net','split_move_lines')}
        assert len(closed)==14
        additional=set()
        if 'step_payroll_oca_api/models/original_type_relations.py' in packets[0]:
            additional={('hr.payroll.structure','schedule_pay'),('hr.payroll.structure.type','struct_ids'),
                ('hr.payroll.structure.type','struct_type_count'),('hr.payroll.structure.type','default_struct_id'),
                ('hr.salary.rule','account_credit'),('hr.salary.rule','account_debit'),
                ('hr.salary.rule','analytic_account_id'),('hr.salary.rule','note')}
            closed|=additional
        assert closed<={(row['model'],row['name']) for row in current['target_metadata']['fields']}
        for name in ('field_differences','selection_value_differences'):
            assert not closed & {(row['model'],row['field']) for row in assessment[name]}
        assert not closed & {(helper.TABLES[row['table']],row['field']) for row in assessment['column_differences']}
        result['configuration_adoption_preflight']={'read_only_evidence_unchanged':True,
            'physical_original_field_contracts_closed':14,'additional_original_field_contracts_closed':len(additional),
            'original_field_contracts_closed':len(closed),
            'source_masters':assessment['source_master_count'],'source_xmlids':assessment['source_xmlid_count'],
            'occupied_ids':len(assessment['occupied_source_ids']),'xmlid_conflicts':len(assessment['xmlid_conflicts']),
            'remaining_field_differences':len(assessment['field_differences']),
            'remaining_column_differences':len(assessment['column_differences']),
            'remaining_selection_differences':len(assessment['selection_value_differences']),
            'adoption_ready':False,'remaining_gates':assessment['remaining_gates']}
        native_file=folder/'native-source.json'
        if native_file.exists():
            proof=json.loads(native_file.read_text())
            assert proof['read_only'] and proof['two_readonly_snapshots_equal']
            assert not any(proof[key] for key in ('orm_loaded','rules_evaluated','historical_payroll_read',
                'salary_formulas_exposed','adoption_authorized','engine_converted','financial_certified'))
            assert proof['native_database']==results['cerro-reference']['database']
            assert proof['capsule_sha256']==hashlib.sha256(capsule.read_bytes()).hexdigest()
            assert proof['tool_sha256']==hashlib.sha256(executed).hexdigest()
            native=proof['native_metadata_before']
            assert native==proof['native_metadata_after'] and native['transaction']==[{'mode':'on'}]
            assert helper.digest(native)==proof['before_metadata_sha256']==proof['after_metadata_sha256']
            for table,rows in sealed['tables'].items():
                assert native['source_hash:'+table]==[{'rows_sha256':rows['rows_sha256']}]
                assert native['row_count:'+table]==[{'row_count':rows['row_count']}]
            attributes={'type':'ttype','relation':'relation','required':'required','readonly':'readonly',
                'store':'store','related':'related','company_dependent':'company_dependent'}
            by_field={(row['model'],row['name']):row for row in native['fields']}
            for field in sealed['field_metadata']:
                assert all(field[key]==by_field[field['model'],field['name']][value] for key,value in attributes.items())
            aliases={(row['module'],row['name']):row for row in native['xmlids']}
            expected={(row['module'],row['name']):row for row in sealed['xmlids']}
            assert aliases.keys()==expected.keys()
            reference_names={('step_simpledigital_oca_security','chile_rule_'+name) for name in ('basic','gross','net')}
            source_aliases={(row['module'],row['name']):row for row in original['original_xmlids']}
            assert reference_names.isdisjoint(source_aliases)
            for key,row in expected.items():
                assert all(row[name]==aliases[key][name] for name in ('module','name','model','res_id','noupdate'))
                if key not in reference_names:
                    assert row==aliases[key]
                    assert all(row[name]==source_aliases[key][name] for name in ('id','module','name','model','res_id'))
            classification=json.loads((folder/'native-xmlid-classification.json').read_text())
            assert classification['identity_before_sha256']==hashlib.sha256((args.evidence/'cerro-reference/identity-before.json').read_bytes()).hexdigest()
            assert classification['native_provenance_sha256']==hashlib.sha256(native_file.read_bytes()).hexdigest()
            assert classification['origin_xmlids_present_before_upgrade']==88 and classification['reference_aliases_absent_before_upgrade']==3
            assert not classification['unexpected_drift']
            hook=classification['adapter_source']
            assert hook['sha256']==hashlib.sha256(source['step_simpledigital_oca_security/hooks.py']).hexdigest()
            result['native_configuration_provenance']={'exact_master_rows':120,'exact_tables':6,
                'origin_xmlid_rows':88,'new_reference_aliases':3,'named_references_and_noupdate_match':True,
                'all_91_metadata_primary_keys_match':False,'native_before_noupdate_not_captured':not all('noupdate' in row for row in original['original_xmlids']),
                'engine_converted':False,'financial_certified':False}
    if security_admission.exists():
        import importlib.util
        folder=security_admission.parent
        executed=(folder/'security-auditor.py').read_bytes()
        expected=source['tools/community/payroll_original_security_admission.py']
        assert executed.replace(b'\r\n',b'\n')==expected.replace(b'\r\n',b'\n')
        proof=json.loads(security_admission.read_text())
        assert proof['tool_sha256']==hashlib.sha256(executed).hexdigest()
        assert proof['capsule_sha256']==hashlib.sha256(capsule.read_bytes()).hexdigest()
        assert proof['target_database']==results['community']['database']
        assert proof['source_database']==sealed['database']
        assert proof['read_only'] and proof['source_configuration_matches_capsule']
        assert not any(proof[key] for key in ('orm_loaded','rules_evaluated','salary_formulas_exposed'))
        sys.path.insert(0,str(repo/'tools/community'))
        spec=importlib.util.spec_from_file_location('security_admission',repo/'tools/community/payroll_original_security_admission.py')
        helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
        plan=helper.preservation_plan(proof['source'],proof['target'])
        assert proof['plan']==plan
        assert not plan['metadata_preservation_admissible'] and plan['blockers']
        assert plan['new_acl_grants']==[] and plan['functional_actor_acceptance_required']
        assert not any(plan[key] for key in ('group_memberships_changed','manager_assigned','field_groups_changed',
            'database_writes','import_authorized','dependency_change_authorized','record_rule_equivalence_certified','engine_converted'))
        result['original_security_admission']={key:plan[key] for key in ('metadata_preservation_admissible','blockers',
            'original_acl_count','original_record_rule_count','new_acl_grants','functional_actor_acceptance_required',
            'record_rule_equivalence_certified','engine_converted')}
    if rule_source.exists():
        proof=json.loads(rule_source.read_text())
        executed=(args.evidence/'rule-source-auditor.py').read_bytes()
        assert proof['auditor_sha256']==hashlib.sha256(executed).hexdigest()
        assert executed.replace(b'\r\n',b'\n')==source['tools/community/hr_rule_source_audit.py'].replace(b'\r\n',b'\n')
        assert proof['provider_license']=='AGPL-3' and proof['source_files_pinned']==52
        assert proof['oca_revision']==results['community']['oca_revision']
        assert not proof['provider_data_essential_rules'] and not proof['oca_data_essential_rules']
        assert {row['code']['text'] for row in proof['oca_demo_essential_rules']}=={'BASIC','GROSS','NET'}
        assert proof['demo_is_not_original_configuration'] and not any(proof[k] for k in ('formulas_exposed','database_reads','financial_certified'))
        result['essential_rule_provenance']={'provider_production':0,'oca_production':0,'oca_demo':3,
                                            'demo_adopted':False,'financial_certified':False}
    if products.exists():
        proof=json.loads(products.read_text())
        executed=(args.evidence/'products-auditor.py').read_bytes()
        assert proof['tool_sha256']==hashlib.sha256(executed).hexdigest()
        assert executed.replace(b'\r\n',b'\n')==source['tools/community/audit_product_frontier.py'].replace(b'\r\n',b'\n')
        assert proof['read_only'] and not any(proof[key] for key in ('orm_loaded','business_data_exported','source_bodies_exported','enterprise_sources_copied'))
        assert set(proof['products'])=={'cerro','steps','sys'}
        result['products']={}
        for name,product in proof['products'].items():
            modules=product['modules'];own=[m for m in modules if m['name'].startswith('step')]
            assert product['installed']==len(modules) and product['own']==len(own)
            assert product['enterprise']==sum(m['license']=='OEEL-1' for m in modules)
            assert product['own_without_source']==[m['name'] for m in own if not m['source_available']]
            assert product['own_without_active_source']==[m['name'] for m in own if not m['active_source_available']]
            result['products'][name]={key:value for key,value in product.items() if key!='modules'}
    if relation_storage.exists():
        proof=json.loads(relation_storage.read_text())
        executed=(relation_storage.parent/'validator.py').read_bytes()
        assert proof['tool_sha256']==hashlib.sha256(executed).hexdigest()
        assert executed.replace(b'\r\n',b'\n')==source['tools/community/validate_payroll_relation_storage.py'].replace(b'\r\n',b'\n')
        old=json.loads((relation_storage.parent/'original-before.json').read_text())
        now=json.loads((relation_storage.parent/'original-after.json').read_text())
        assert old==now and len(old)==proof['original_contracts_preserved']
        assert proof['idempotence_verified'] and proof['backup_decoded'] and proof['original_metadata_preserved']
        assert not any(proof[k] for k in ('writes_to_source','orm_loaded','paid_payroll_recomputed','engine_converted','financial_certified'))
        assert set(proof['tables'])=={'hr_payslip_worked_days','hr_payslip_input'}
        for table,row in proof['tables'].items():
            assert old[table]['rows']==row['rows'] and not {'code','contract_id'} & set(row['original_columns'])
        for filename in ('storage-after-restore.json','storage-after.json'):
            capacity=json.loads((relation_storage.parent/filename).read_text())
            assert capacity['postgres']['available_bytes']>=5*1024**3 and capacity['artifacts']['available_bytes']>=2*1024**3
        result['sys_related_storage']={'original_contracts_preserved':len(old),
            'rows':{table:row['rows'] for table,row in proof['tables'].items()},
            'idempotence_verified':True,'orm_loaded':False,'engine_converted':False,'financial_certified':False}
        if proof.get('contract_fks_prepared'):
            initial=json.loads((relation_storage.parent/'foreign-keys-before.json').read_text())
            final=json.loads((relation_storage.parent/'foreign-keys-after.json').read_text())
            target=json.loads((relation_storage.parent/'community-contract.json').read_text())
            indexed={row['oid']:row for row in final}
            assert all(indexed.get(row['oid'])==row for row in initial)
            assert proof['original_foreign_keys_preserved'] and not proof['orm_metadata_adopted']
            assert not proof['native_nullability_changed']
            assert target['read_only'] and not target['orm_loaded'] and target['enterprise']==0
            assert set(target['modules'])=={'payroll','step_payroll_oca_api'}
            assert len(target['fields'])==4
            for row in target['fields']:
                assert row['store'] and row['required'] and not row['related']
                assert (row['type'],row['relation'],row['on_delete'])==(
                    ('char',None,None) if row['name']=='code' else ('many2one','hr.contract','restrict'))
            for table in ('hr_payslip_input','hr_payslip_worked_days'):
                name=table+'_contract_id_fkey'
                for rows in (final,target['foreign_keys']):
                    match=[row for row in rows if row['table']==table and row['name']==name]
                    assert len(match)==1 and match[0]['validated']
                    assert match[0]['definition']=='FOREIGN KEY (contract_id) REFERENCES hr_contract(id) ON DELETE RESTRICT'
            assert {row['name'] for row in final if row['oid'] not in {item['oid'] for item in initial}}<= {
                'hr_payslip_input_contract_id_fkey','hr_payslip_worked_days_contract_id_fkey'}
            result['sys_related_storage'].update(contract_fks_prepared=True,original_foreign_keys_preserved=True,
                                                 orm_metadata_adopted=False,native_nullability_changed=False)
    if registry.exists():
        executed=(registry/'validator.py').read_bytes()
        assert executed.replace(b'\r\n',b'\n')==source['tools/community/validate_adoption_registry.py'].replace(b'\r\n',b'\n')
        result['loaded_adoption_registry']={}
        for mode in ('community','cerro-reference'):
            folder=registry/mode
            proof=json.loads((folder/'passed.json').read_text())
            reports=json.loads((folder/'registry.json').read_text())
            before=json.loads((folder/'business-before.json').read_text());after=json.loads((folder/'business-after.json').read_text())
            assert before==after and len(before)==proof['exact_tables_and_counters_preserved']
            assert proof['runner_sha256']==hashlib.sha256(executed).hexdigest()
            assert proof['source_packet_sha256']==results[mode]['source_files_sha256']
            assert proof['database']==results[mode]['database'] and proof['read_only'] and proof['metadata_only']
            assert not any(proof[key] for key in ('upgraded','business_records_read','source_bodies_exported','functional_conversion_certified'))
            for name,digest in proof['helpers_sha256'].items():
                helper=(registry/name).read_bytes()
                assert hashlib.sha256(helper).hexdigest()==digest
                assert helper.replace(b'\r\n',b'\n')==source['tools/community/'+name].replace(b'\r\n',b'\n')
            batch,caf=reports['batch'],reports['caf']
            assert batch['read_only'] and not batch['business_records_read'] and not batch['functional_provider_certified']
            assert caf['transaction_read_only'] and not any(caf[key] for key in (
                'orm_records_accessed','payloads_read','provider_methods_called','adoption_ready'))
            if mode=='community':
                if custody_grouping:
                    assert batch['model_present'] and batch['table']=='account_batch_payment'
                    assert caf['binary_attachment_policy_proven'] and len(caf['fields'])==14
                    assert not batch['related_providers']['bank.rec.widget']['present']
                    assert batch['method_signatures']['create']['module'].startswith('odoo.addons.step_batch_payment_core.')
                else:assert not batch['model_present'] and not caf['model_present']
                target=reports['payroll_relations']
                assert target['read_only'] and target['enterprise']==0 and not target['orm_loaded']
                if relation_storage.exists() and json.loads(relation_storage.read_text()).get('contract_fks_prepared'):
                    previous=json.loads((relation_storage.parent/'community-contract.json').read_text())
                    signature=lambda report:[{key:value for key,value in row.items() if key!='id'} for row in report['fields']]
                    assert signature(previous)==signature(target),'Prepared FK semantics changed in the latest OCA registry'
            else:
                assert batch['model_present'] and caf['binary_attachment_policy_proven']
                assert not caf['folio_allocation_ready'] and not caf['payload_storage_preservation_verified']
            result['loaded_adoption_registry'][mode]={'metadata_only':True,'exact_tables_and_counters_preserved':len(before),
                'caf_attachment_metadata':bool(caf.get('binary_attachment_policy_proven')),'functional_conversion_certified':False}
    if accelerated:
        assert results['cerro-reference']['accelerated']
        api_count=results['community'].get('api_test_count',63)
        base_count=results['community'].get('base_test_count',7)
        assert results['community']['expected_test_count']==(313 if custody_grouping else 259)+(api_count-63)+(base_count-7)
        assert results['cerro-reference']['expected_test_count']==(244 if custody_grouping else 215)+(results['cerro-reference'].get('reference_test_count',25)-25)
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
            assert len(finance['aliases'])==15 and finance['payment_formats_use_original_model'] and not finance['batch_conversion_certified']
            assert len(finance['multicurrency_legacy_aliases'])==37
        result['accelerated']={'hr_consumers_installed':list(hr_modules),'bank_aliases_preserved':15,
            'multicurrency_aliases_preserved':37,
            'caf_custody_provider':custody_grouping,'draft_grouping_provider':custody_grouping,
            'caf_authenticity_core_only':not custody_grouping,'full_dte_certified':False,'batch_conversion_certified':False}
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
            memberships=sum(row['rule_count'] for row in value['reports'])
            known=all('direct_rule_ids' in row and 'inherited_rule_ids' in row for row in value['reports'])
            distinct={ident for row in value['reports'] for ident in row.get('direct_rule_ids',[])+row.get('inherited_rule_ids',[])}
            reports[mode]={'normal_actor':True,'total_rules':len(distinct) if known else memberships,
                'effective_rule_memberships':memberships,'distinct_rule_ids_available':known,
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
