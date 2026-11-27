"""Check the controlled SyS-to-Cerro payroll trial without distributing the source payslip."""
import argparse
import json
from pathlib import Path


NATIVE = 'MANAGEMENT_QA_CERRO_HR_FIELDS_20261126U40V'
COMMUNITY = 'COMMUNITY_PAYROLL_API_CERRO_SCOPE_20261126U40J'
REVIEW = 'COMMUNITY_PAYROLL_CERRO_REVIEW_20261126U42F'


def validate_cases(native, candidate, *, supplied_month):
    if not __debug__ or (native['database'], candidate['database']) != (NATIVE, COMMUNITY):
        raise ValueError('Use the two established private Cerro restores.')
    if native['input_digest'] != candidate['input_digest']:
        raise ValueError('Different source cases were used.')

    def index(receipt):
        trials = receipt['trials']
        rows = {row['trial_target_analytic_id']: row for row in trials}
        if len(rows) != len(trials) or len(rows) != 17:
            raise ValueError('The reviewed account population changed.')
        for row in trials:
            assert row['database'] == receipt['database'] and row['input_digest'] == receipt['input_digest']
            assert row['calendar_matches_reference'] and not row['source_analytic_link_matched']
            assert row['missing_contract_fields'] == []
            assert row['stored_work_entries'] == 62 and row['stored_day_lines'] == 1
            assert bool(row.get('monthly_tax_reference_matches')) == supplied_month
        return rows

    left, right = index(native), index(candidate)
    assert left.keys() == right.keys()
    for row in right.values():
        assert (row['phase'], row['error'], row['method']) == ('compute', 'UserError', 'validate_configuration')
        assert row['configuration_codes'] == ['GROSS_DISCONNECTED_FROM_BASIC']
    for row in left.values():
        if supplied_month:
            assert row['phase'] == 'calculated' and row['lines'] > 0 and not row['matches_saved_sys']
            levels = row['essential_lines']
            assert all(levels[code]['count'] == 1 for code in ('BASIC', 'GROSS', 'NET'))
            assert levels['BASIC']['positive_total'] and levels['NET']['positive_total']
            assert not levels['GROSS']['positive_total']
        else:
            assert (row['phase'], row['error'], row['origin'], row['line']) == (
                'compute', 'UserError', 'l10n_cl_simpledigital_payroll/models/hr_payslip.py', 98)
    if supplied_month:
        assert len({row['result'] for row in left.values()}) == 1
    return {'accounts_checked': len(left), 'work_entries': 62, 'native_calculated': len(left) if supplied_month else 0,
            'community_refused_structure': len(right), 'financially_certified': False}


def validate_review(native, candidate):
    if not __debug__ or (native['database'], candidate['database']) != (NATIVE, REVIEW):
        raise ValueError('Use the native Cerro and restored contract-review package.')
    for doc in (native, candidate):
        missing = doc['without_analytic']
        assert missing['database'] == doc['database'] and missing['phase'] == 'compute'
        assert missing['missing_contract_fields'] == ['analytic_account_id']
        assert missing['pending_review_exercised']
        assert missing['direct_clear_rejected'] and missing['review_confirmation'] == 'refused'
        assert missing['origin'].endswith('/step_payroll_engine_transition/models.py') and missing['line'] == 64
        trials = doc['with_analytic']
        assert len(trials) == len({r['trial_target_analytic_id'] for r in trials}) == 17
        for row in trials:
            assert row['database'] == doc['database'] and row['input_digest'] == missing['input_digest']
            assert row['calendar_matches_reference'] and row['stored_work_entries'] == 62
            assert row['phase'] == 'compute' and row['missing_contract_fields'] == []
            assert row['pending_review_exercised']
            assert row['direct_clear_rejected'] and row['review_confirmation'] == 'accepted'
    assert native['without_analytic']['input_digest'] == candidate['without_analytic']['input_digest']
    assert {r['trial_target_analytic_id'] for r in native['with_analytic']} == {
        r['trial_target_analytic_id'] for r in candidate['with_analytic']}
    return {'complete_contracts_reviewed_per_engine': 17, 'incomplete_contracts_refused_per_engine': 1,
            'direct_clearing_refused_per_engine': 18}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('native', type=Path)
    parser.add_argument('community', type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--supplied-month', action='store_true')
    mode.add_argument('--review-actions', action='store_true')
    args = parser.parse_args()
    native, community = (json.loads(path.read_bytes()) for path in (args.native, args.community))
    result = (validate_review(native, community) if args.review_actions else
              validate_cases(native, community, supplied_month=args.supplied_month))
    print(json.dumps(result, sort_keys=True))
