"""Recheck the isolated native observation; never claim refund equivalence."""
import hashlib
import json


def verify_native_payroll_tags(folder, source):
    def read(name):
        return json.loads((folder/name).read_text())
    proof=read('passed.json')
    assert proof['source_database']=='MANAGEMENT_QA_CERRO_PAYROLL_API_PROPERTIES_20261029F'
    assert all(proof[key] for key in ('backup_decoded','source_unchanged','source_filestore_unchanged',
        'observation_only','isolated_network_namespace','postgres_unix_socket','official_test_thread_marker'))
    assert not any(proof[key] for key in ('fresh_production_acceptance','engine_converted','writes_to_source'))
    for exported,original,key in (
        ('probe.py','tools/community/probe_native_payroll_tags.py','payload_sha256'),
        ('runner.py','tools/community/observe_native_payroll_tags.py','runner_sha256')):
        executed=(folder/exported).read_bytes()
        assert hashlib.sha256(executed).hexdigest()==proof[key]
        assert executed.replace(b'\r\n',b'\n')==source[original].replace(b'\r\n',b'\n')
    export=folder/'runner-export.json'
    if export.exists():
        derivation=read('runner-export.json')
        archived=source['tools/community/observe_native_payroll_tags.py']
        assert derivation['source_archive_sha256']==hashlib.sha256(archived).hexdigest()
        assert derivation['executed_runner_sha256']==proof['runner_sha256']
        assert derivation['execution_seal_changed'] is False
        assert derivation['transformation'] in ('identity','CRLF-to-LF')
        reconstructed=archived if derivation['transformation']=='identity' else archived.replace(b'\r\n',b'\n')
        assert (folder/'runner.py').read_bytes()==reconstructed
    blob=(folder/'observations.json').read_bytes()
    assert hashlib.sha256(blob).hexdigest()==proof['observations_sha256']
    before=read('before.json')
    assert before==read('after.json') and len(before)==proof['original_contracts_preserved']
    restored=read('restored-before-neutralization.json')
    assert restored==read('source-before.json') and before.keys()==restored.keys()
    assert all(before[name]==value for name,value in restored.items() if name not in ('ir_cron','ir_mail_server'))
    neutralized=read('neutralized-activation-ids.json')
    assert set(neutralized)=={'ir_cron','ir_mail_server'}
    assert all(type(ident) is int and ident>0 for ids in neutralized.values() for ident in ids)
    data=read('observations.json')
    assert data['business_fixture_rolled_back'] and not data['equivalence_certified'] and not data['engine_replaced']
    assert len(data['metadata'])==4
    assert {(row['model'],row['name']) for row in data['metadata']}=={
        (model,name) for model in ('hr.salary.rule','hr.payslip.line') for name in ('debit_tag_ids','credit_tag_ids')}
    for row in data['metadata']:
        assert row['name'] in ('debit_tag_ids','credit_tag_ids')
        assert row['type']=='many2many' and row['comodel']=='account.account.tag'
        assert row['related'] is None and row['domain']==[] and row['domain_expression'] is None
        if row['model']=='hr.salary.rule':
            assert row['store'] and row['copy'] and not row['readonly'] and not row['computed']
            assert row['relation']=='hr_salary_rule_'+row['name'].split('_')[0]+'_tag_rel'
            assert (row['column1'],row['column2'])==('hr_salary_rule_id','account_account_tag_id')
        else:
            assert row['model']=='hr.payslip.line'
            assert row['readonly'] and row['computed'] and not row['store'] and not row['copy']
            assert row['relation'] is row['column1'] is row['column2'] is None
    accounts,tags=data['fixture_account_ids'],data['fixture_tag_ids']
    cases=data['observations']
    assert len(cases)==4 and {(c['amount'],c['credit_note']) for c in cases}=={(100,False),(-100,False),(100,True),(-100,True)}
    for case in cases:
        assert case['normal_actor'] and case['state']=='done'
        assert case['credit_note_before'] is case['credit_note_after'] is case['credit_note']
        assert case['salary_before']==case['salary_after'] and case['line_tags_before']==case['line_tags_after']
        assert len(case['move'])==1 and case['move'][0]['state']=='draft'
        lines=case['move_lines'];assert len(lines)==2
        assert sum(row['balance'] for row in lines)==0 and sum(row['debit'] for row in lines)==abs(case['amount'])
        for side,multiplier in (('debit',1),('credit',-1)):
            matches=[row for row in lines if row['account_id'][0]==accounts[side]]
            assert len(matches)==1
            row=matches[0]
            assert row['balance']==case['amount']*multiplier
            assert row['tax_tag_ids']==[tags[side]] and row['tax_tag_invert'] is False
    return {'cases':4,'normal_actor':True,'fixture_rolled_back':True,'external_network_disabled':True,
        'tags_follow_configured_account':True,'native_credit_note_preserves_observed_sign':True,
        'native_tax_tag_invert':False,'native_move_state':'draft','native_posting_certified':False,
        'refund_equivalence_certified':False,'fresh_production_acceptance':False}
