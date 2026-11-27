"""Compare ordinary expenses, receipts, accounting entries and permissions with the private Steps original."""
import argparse
import json
from pathlib import Path


PAYROLL_FIELDS = {'payslip_id', 'refund_in_payslip'}
PAYROLL_ACTIONS = {'action_report_in_next_payslip', 'action_remove_from_payslip', 'action_open_payslip'}
OCR_FIELDS = {'extract_can_show_send_button', 'extract_document_uuid', 'extract_error_message', 'extract_state'}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def verify(native, candidate, native_trial, candidate_trial, native_visibility, candidate_visibility):
    require(native['database'] == 'MANAGEMENT_QA_STEPS_CRM_20261126U42C' and
            candidate['database'] == 'COMMUNITY_STEPS_EXPENSE_20261127U50E', 'Unexpected expense evidence source')
    require(len(native['cases']) == len(candidate['cases']) == 7, 'Missing original user scope')
    for original, actual in zip(native['cases'], candidate['cases']):
        require(all(original[key] == actual[key] for key in ('actor', 'companies', 'files')), 'Expense owner or file access differs')
        require(original['models'].keys() == actual['models'].keys(), 'Expense model inventory differs')
        for model, record in original['models'].items():
            observed = actual['models'][model]
            require({k: v for k, v in record.items() if k != 'fields'} ==
                    {k: v for k, v in observed.items() if k != 'fields'}, 'Expense access rights or records differ')
            omitted = PAYROLL_FIELDS if model == 'hr.expense.sheet' else set()
            require({k: v for k, v in record.get('fields', {}).items() if k not in omitted} == observed.get('fields', {}),
                    'Historical expense field differs')
        require(original['menus'].keys() == actual['menus'].keys(), 'Expense menu routes differ')
        for key, menu in original['menus'].items():
            received = actual['menus'][key]
            require({k: v for k, v in menu.items() if k not in ('displayed', 'buttons', 'opened')} ==
                    {k: v for k, v in received.items() if k not in ('displayed', 'buttons', 'opened')},
                    'Expense form, posting link or undefined client field differs')
            if not menu['visible']:
                continue
            require(not any(received['view_fields_undefined'].values()), 'Undefined field in a linked expense view')
            require(not received['undefined'] and set(menu['displayed']) - PAYROLL_FIELDS - OCR_FIELDS == set(received['displayed']) and
                    set(menu['buttons']) - PAYROLL_ACTIONS - {'action_manual_send_for_digitization'} == set(received['buttons']),
                    'Unexplained change in expense form')
            require({k: v for k, v in menu.get('opened', {}).items() if k not in PAYROLL_FIELDS} ==
                    received.get('opened', {}), 'Expense form records differ')
    complete, = [c for c in candidate['cases'] if c['actor'] == 2 and set(c['companies']) == {1, 2}]
    entries = complete['menus']['menu_hr_expense_report']['posted_entries']
    require(all(len(m['ids']) == 3 for m in complete['models'].values()) and len(entries) == 3,
            'Incomplete approved expenses or their posted entries')
    physical = [v for group in complete['files'].values() for v in group.values()]
    require(len(physical) == 2 and all(isinstance(v, list) and v[1] > 0 for v in physical), 'Missing original expense receipts')
    require(native_visibility == candidate_visibility and native_visibility == {'linked_examples': 2,
            'scopes': [[2, 2, 2, [True, True]], [10, 2, 1, [True, False]]], 'history_unchanged': True},
            'Expense document count or file permissions differ')
    require(native_trial == candidate_trial and native_trial['history_unchanged'] and
            native_trial['states'] == ['draft', 'submit', 'approve', 'post'] and native_trial['posting'] == 'posted' and
            native_trial['payment_mode'] == 'own_account' and native_trial['posted_lines'] == 2,
            'Employee expense submission, approval or journal entry differs')
    return {'contexts': 7, 'expenses': 3, 'reports': 3, 'posted_entries': 3, 'attachments': 2,
            'attachment_bytes': sum(v[1] for v in physical), 'new_report_states': native_trial['states'],
            'new_entry_lines': native_trial['posted_lines'], 'missing_client_fields': 0,
            'payroll_enabled_in_steps': False, 'historical_ocr_requests': 0, 'linked_document_visibility': [2, 1]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('receipts', nargs=6, type=Path)
    print(json.dumps(verify(*(json.loads(p.read_bytes()) for p in parser.parse_args().receipts)), sort_keys=True))
