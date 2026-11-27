"""Verify Steps' two manual payment workflows and the historical payments and reconciliations."""
import argparse
import json
from pathlib import Path


def verify(native, candidate, native_trial, candidate_trial):
    if (native['database']!='MANAGEMENT_QA_STEPS_CRM_20261126U42C' or candidate['database'] not in
            ('COMMUNITY_STEPS_CRM_FISCAL_20261127U45F','COMMUNITY_STEPS_CRM_INTEGRATED_20261127U46A') or
            len(native['cases'])!=7 or native['cases']!=candidate['cases']):
        raise ValueError('Historical payment forms, records, fields or permissions differ')
    all_companies,=[case for case in native['cases'] if case['actor']==2 and set(case['companies'])=={1,2}]
    counts={m:r['count'] for m,r in all_companies['models'].items()}
    if counts!={'account.payment':45,'account.partial.reconcile':42,'account.full.reconcile':25}:
        raise ValueError('Incomplete historical payment and reconciliation inventory')
    menus=all_companies['menus']
    if (menus['account.menu_action_account_payments_receivable']['count']!=34 or
            menus['account.menu_action_account_payments_payable']['count']!=11):
        raise ValueError('Default payment menu filters differ')
    if not native_trial['history_unchanged'] or candidate_trial!=native_trial:
        raise ValueError('The manual registration, validation or resulting ledger state differs')
    pending, posted = native_trial['default'],native_trial['configured']
    if (pending['configured'] or pending['state']!='in_process' or pending['move_posting'] or
            pending['invoice_state']!='in_payment' or pending['validated']['payment']!='paid' or
            not posted['configured'] or posted['state']!='paid' or posted['move_posting']!='posted' or
            posted['invoice_state']!='paid' or not posted['reconciled'] or
            not all(row['reopened'] and row['invoice_link'] and row['method']=='manual' for row in (pending,posted))):
        raise ValueError('Expected a pending payment and a separately posted and reconciled payment')
    return {'account_payments':45,'partial_reconciliations':42,'full_reconciliations':25,'contexts':7,
            'inbound':34,'outbound':11,'pending_payment':pending['state'],'configured_payment':posted['state'],
            'historical_business_rows_unchanged':True}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('native','candidate','native_trial','candidate_trial'):
        parser.add_argument(name,type=Path)
    args=parser.parse_args()
    print(json.dumps(verify(*(json.loads(path.read_bytes()) for path in vars(args).values()))))
