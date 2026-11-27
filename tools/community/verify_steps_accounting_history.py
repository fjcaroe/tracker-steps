"""Verify the original Steps accounting identities, balances, permissions and visible historical forms."""
import argparse
import json
from pathlib import Path


def compare_values(original, candidate):
    assert candidate.keys()<=original.keys()
    assert all(original[key]==value for key,value in candidate.items())
    return sorted(original.keys()-candidate.keys())


def compare(native, community):
    assert __debug__ and native['database']=='MANAGEMENT_QA_STEPS_CRM_20261126U42C'
    assert community['database'] in ('COMMUNITY_STEPS_CRM_DOC_20261127U44P','COMMUNITY_STEPS_CRM_SUPPORT_20261127U44H3',
                                     'COMMUNITY_STEPS_EXPENSE_20261127U50E', 'COMMUNITY_STEPS_CRM_FISCAL_20261127U45F','COMMUNITY_STEPS_CRM_INTEGRATED_20261127U46A')
    assert all(native[k]==community[k]==n for k,n in [('moves',86),('posted',84),('lines',211)])
    assert len(native['cases'])==len(community['cases'])==7
    missing = {}
    omitted_form_fields = set()
    opened = 0
    for left,right in zip(native['cases'],community['cases']):
        assert all(left[k]==right[k] for k in ('actor','companies','administrator'))
        if 'document_actions' in left and right.get('document_actions', {}).get('registered'):
            assert left['document_actions'] == right['document_actions']
        if 'archived_files' in left or 'archived_files' in right:
            assert left['archived_files']['registered']
            if right['archived_files']['registered']:
                assert left['archived_files']==right['archived_files']
        assert left['models'].keys()==right['models'].keys()
        for model,original in left['models'].items():
            candidate = right['models'][model]
            assert original.keys()==candidate.keys()
            assert all(original[k]==candidate[k] for k in original if k!='fields')
            if original['read']:
                missing.setdefault(model,set()).update(compare_values(original['fields'],candidate['fields']))
        original_menus, candidate_menus = left['menus'], right['menus']
        if original_menus is None:
            assert candidate_menus is None
            continue
        assert original_menus.keys()==candidate_menus.keys()
        for key,original in original_menus.items():
            candidate = candidate_menus[key]
            assert candidate.keys()==original.keys()
            assert all(candidate[k]==original[k] for k in original if k not in ('form_fields','web_values'))
            if not original['visible']:
                continue
            omitted_form_fields.update(set(original['form_fields'])-set(candidate['form_fields']))
            if 'opened' in original:
                missing['account.move'].update(compare_values(original['web_values'],candidate['web_values']))
                opened += 1
    assert opened>0
    return {'historical_entries':native['moves'],'posted_entries':native['posted'],'lines':native['lines'],
            'contexts':7,'opened_forms':opened,'missing_model_fields':{k:sorted(v) for k,v in missing.items()},
            'missing_form_fields':sorted(omitted_form_fields)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('native',type=Path)
    parser.add_argument('candidate',type=Path)
    args=parser.parse_args()
    print(json.dumps(compare(json.loads(args.native.read_bytes()),json.loads(args.candidate.read_bytes()))))
