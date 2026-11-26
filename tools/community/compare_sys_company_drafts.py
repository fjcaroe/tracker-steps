"""Compare private native and Community recalculations of each company's latest payroll month."""
import argparse
import json
from collections import Counter
from pathlib import Path


def compare(native, community, accounting=False, require_review_policy=False):
    if not native['native'] or community['native'] or native['uid'] != community['uid']:
        raise ValueError('Expected independent native and Community operator receipts')

    def index(receipt):
        cases = {(row['company'], row['period'], row['source']): row for row in receipt['samples']}
        if not cases or len(cases) != len(receipt['samples']):
            raise ValueError('Missing or repeated source payslip')
        return cases

    original, candidate = index(native), index(community)
    if original.keys() != candidate.keys():
        raise ValueError('Different source cohorts')
    companies = {}
    for key, source in original.items():
        peer = candidate[key]
        counts = companies.setdefault(key[0], Counter())
        counts['selected'] += 1
        if 'draft' not in source:
            counts['native_rejected'] += 1
            same_policy = (not require_review_policy or
                           source.get('policy') == peer.get('policy') == 'native_contract_review')
            if 'error' in peer and 'draft' not in peer and same_policy:
                counts['both_rejected'] += 1
            else:
                counts['rejection_differs'] += 1
        elif 'error' in peer:
            counts['community_rejected'] += 1
        elif ('draft' in peer and source['draft'] == peer['draft'] and source['lines'] == peer['lines']
              and source['stored'] == peer['stored'] and source['equals_stored'] == peer['equals_stored']):
            counts['same_calculation'] += 1
            counts['matching_lines'] += source['lines']
            counts['matches_closed' if source['equals_stored'] else 'native_differs_from_closed'] += 1
            if accounting:
                expected = source.get('confirmation')
                actual = peer.get('confirmation')
                if (expected and expected == actual and expected['move_state'] == 'draft' and
                        expected['move_lines'] == 0 and expected['closed_payroll_amounts_unchanged']):
                    counts['matching_confirmations'] += 1
        else:
            counts['different_calculation'] += 1
    return companies


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('native', type=Path)
    parser.add_argument('community', type=Path)
    parser.add_argument('--accounting', action='store_true')
    parser.add_argument('--require-review-policy', action='store_true')
    args = parser.parse_args()
    companies = compare(json.loads(args.native.read_bytes()), json.loads(args.community.read_bytes()),
                        accounting=args.accounting, require_review_policy=args.require_review_policy)
    print(json.dumps(companies, sort_keys=True))
    if any(row['selected'] != row['same_calculation'] + row['both_rejected'] for row in companies.values()):
        raise SystemExit(1)
    if args.accounting and any(row['same_calculation'] != row['matching_confirmations'] for row in companies.values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
