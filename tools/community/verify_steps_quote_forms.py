"""Verify the normal quotation workflow on the Steps candidate with the unused workbook UI archived."""
import argparse
import json
from pathlib import Path


def verify(native_read, native_trial, candidate):
    if not __debug__:
        raise ValueError('Assertion checks must be enabled.')
    original = 'MANAGEMENT_QA_STEPS_CRM_20261126U42C'
    target = 'COMMUNITY_STEPS_CRM_QUOTE_20261127U42A'
    assert native_read['database'] == native_trial['database'] == original
    storage, received, trial = (candidate[name] for name in ('storage','read','trial'))
    assert storage['database'] == received['database'] == trial['database'] == target
    assert (storage['inactive_views'],storage['inactive_menu'],storage['original_action_retained']) == (
        [1443,1444,1445,1446],329,481)
    assert storage['stored_sales_workbooks'] == storage['assigned_workbooks'] == 0
    assert (storage['tables'],storage['rows'],storage['original_counters']) == (1112,163133,804)
    assert storage['differences']['public_tables'] == ['ir_ui_menu','ir_ui_view']
    assert not any(items for name,items in storage['differences'].items() if name != 'public_tables')
    def omit(data, ignored):
        return {key:value for key,value in data.items() if key not in ignored}
    assert omit(received, {'database','quote_form_fields'}) == omit(native_read, {'database','quote_form_fields'})
    fields = set(native_read['quote_form_fields'])
    assert len(fields) == 120 and set(received['quote_form_fields']) == fields - {'spreadsheet_id','spreadsheet_template_id'}
    assert omit(trial, {'database'}) == omit(native_trial, {'database'})
    assert trial['saved_and_reopened'] and trial['rolled_back'] and trial['state'] == 'draft'
    assert (trial['created_from_action'],trial['reopened_from_action'],trial['original_orders']) == (526,460,4)
    return {'historic_sales_sha256':received['historic_sales'], 'new_quote_sha256':trial['terms_and_amounts'],
            'quote_form_fields':len(received['quote_form_fields']), 'attachments':received['attachments']['sales']['allowed']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('native-read','native-trial','candidate'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(*[json.loads(path.read_bytes())
                              for path in (args.native_read,args.native_trial,args.candidate)])))
