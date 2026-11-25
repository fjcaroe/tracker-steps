"""Compare private draft receipts from the same anchored pair."""
import argparse
from collections import defaultdict
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path


def lines_by_rule(rows):
    result = defaultdict(list)
    for rule, *values in rows:
        amounts = tuple(Decimal(value) for value in values)
        assert all(value.is_finite() for value in amounts)
        result[rule].append(amounts)
    return {rule: sorted(lines) for rule, lines in result.items()}


def compare_case(before, after):
    assert before['fixture_rolled_back'] and after['fixture_rolled_back']
    phases = [before['phase'], after['phase']]
    result = {'phases': phases, 'errors': [before.get('error_type'), after.get('error_type')],
              'exact': False}
    if 'fixture' in before or 'fixture' in after:
        assert before['fixture'] == after['fixture'], 'Draft basis fixtures differ'
        result['fixture'] = before['fixture']
    measurements = ('inputs', 'original_work_entries', 'worked_days_final', 'original_rule_ids')
    result['original_inputs_days_and_rules_equal'] = all(
        key in before and key in after and before[key] == after[key] for key in measurements)
    result['generated_days_equal'] = ('generated_days' in before and
                                       before['generated_days'] == after.get('generated_days'))
    if phases == ['complete', 'complete']:
        original, target = lines_by_rule(before['lines']), lines_by_rule(after['lines'])
        result['compared_original_rule_count'] = len(original.keys() | target.keys())
        result['differences'] = []
        for rule in sorted(original.keys() | target.keys()):
            native_rows, target_rows = original.get(rule, []), target.get(rule, [])
            if native_rows != target_rows:
                result['differences'].append({'rule': rule, 'native_rows': len(native_rows),
                    'community_rows': len(target_rows),
                    'native_total': str(sum(row[-1] for row in native_rows)),
                    'community_total': str(sum(row[-1] for row in target_rows))})
        result['exact'] = result['original_inputs_days_and_rules_equal'] and not result['differences']
    if 'basis_before_compute' in before and 'basis_before_compute' in after:
        result['basis'] = {key: {'native': before.get(key), 'community': after.get(key)}
                           for key in ('basis_before_compute', 'basis_after_compute')}
        result['exact'] &= all(pair['native'] == pair['community'] for pair in result['basis'].values())
    if 'mutations' in before or 'mutations' in after:
        result['mutations'] = {'native': before.get('mutations'), 'community': after.get('mutations')}
        result['exact'] &= result['mutations']['native'] == result['mutations']['community']
    if 'stored_ytd' in before or 'stored_ytd' in after:
        result['stored_ytd_exact'] = before.get('stored_ytd') == after.get('stored_ytd')
        result['exact'] &= result['stored_ytd_exact']
    return result


def compare(native, community, plan):
    assert native['database'] == plan['reference_database'] and community['database'] == plan['database']
    assert native['community'] is False and community['community'] is True
    assert native['operator_uid'] == community['operator_uid'] == 7
    assert native['drafts_only'] and community['drafts_only']
    results = []
    native_cases = {case['structure']: case for case in native['cases']}
    target_cases = {case['structure']: case for case in community['cases']}
    assert len(native['cases']) == len(community['cases']) == 2
    assert set(native_cases) == set(target_cases) == {2, 4}
    for ident in sorted(native_cases):
        before, after = native_cases[ident], target_cases[ident]
        result = {'structure': ident, **compare_case(before, after)}
        if 'native_days_replay' in after:
            result['native_days_replay'] = compare_case(before, after['native_days_replay'])
        results.append(result)
    native_basis = native.get('basis_cases', {})
    target_basis = community.get('basis_cases', {})
    assert native_basis.keys() == target_basis.keys()
    basis_cases = {name: compare_case(native_basis[name], target_basis[name]) for name in native_basis}
    ytd = {}
    if 'active_ytd' in native or 'active_ytd' in community:
        original, target = native['active_ytd'], community['active_ytd']
        assert all(row['fixture_rolled_back'] and row['excluded_open_period']
                   for row in (original, target))
        assert original['activation_in_memory'] is False and target['activation_in_memory'] is True
        ytd = {'same_contract_exact': all(original[key] == target[key]
                                         for key in ('baseline', 'same_contract')),
               'native_new_contract': original['new_contract'],
               'community_new_contract_rejected': target.get('new_contract_rejected', False)}
    return {'schema': 1, 'pair': [native['database'], community['database']],
            'source_dump_sha256': plan['source_dump_sha256'], 'active_ytd': ytd,
            'cases': results, 'basis_cases': basis_cases, 'all_compared_drafts_exact': all(
                row['exact'] and row['generated_days_equal'] for row in [*results, *basis_cases.values()]),
            'all_rules_certified': False, 'financial_certified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', type=Path)
    args = parser.parse_args()
    stage = args.stage.resolve()
    assert stage.is_relative_to('/opt/steps-validation') and stage.name == 'anchor'
    files = [stage / 'native-witness/original-draft_amounts-required.json',
             stage / 'original-draft_amounts-required.json', stage / 'handover-plan.json']
    bodies = [path.read_bytes() for path in files]
    result = compare(*(json.loads(body) for body in bodies))
    result['evidence_sha256'] = [hashlib.sha256(body).hexdigest() for body in bodies]
    output = stage / 'draft-amount-comparison.json'
    with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps([{key: row[key] for key in ('structure', 'phases', 'exact')} for row in result['cases']]))


if __name__ == '__main__':
    main()
