"""Verify independent native and Community receipts for the eleven October batch closures."""
import argparse
import json
from pathlib import Path


def compare(reference, candidate):
    if set(reference) != set(candidate) or len(reference) != 11:
        raise ValueError('Expected the eleven original payroll companies in both receipts')
    slips = 0
    for company, source in reference.items():
        actual = candidate[company]
        if actual != source or 'error' in actual:
            raise ValueError('Batch calculations or transitions differ for company ' + company)
        closed = actual['action_validate']
        count = len(closed['amounts'])
        if not (count and closed['headers_match'] and closed['batch'] == 'close' and not closed['batch_move']
                and closed['slips'] == {'done': count} and closed['moves'] == count
                and closed['move_states'] == {'draft': count} and closed['move_lines'] == 0):
            raise ValueError('Incomplete closing and accounting evidence for company ' + company)
        slips += count
    if slips != 130:
        raise ValueError('Unexpected number of calculated payrolls')
    return {'companies': len(reference), 'payslips': slips, 'matching_draft_moves': slips}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('native', type=Path)
    parser.add_argument('community', type=Path)
    args = parser.parse_args()
    print(json.dumps(compare(json.loads(args.native.read_bytes()), json.loads(args.community.read_bytes()))))
