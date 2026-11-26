"""Verify independently generated native and Community receipts for the SyS October cohort."""
import argparse
import json
from pathlib import Path


def match(native, community):
    if not native['native'] or community['native'] or not community['new_draft_calculated']:
        raise ValueError('A native reference and calculated Community drafts are required')
    originals, candidates = native['samples'], community['samples']
    if len(originals) != 6 or len(candidates) != 6:
        raise ValueError('Expected five unmodified cases and one additional movement')
    totals = []
    for original, candidate in zip(originals,candidates,strict=True):
        if (original.get('error') or candidate.get('error') or not original.get('events') or
                not original.get('lines') or not original.get('result_sha256')):
            raise ValueError('Missing successful evaluation')
        for key in ('slip','synthetic_movement','events','lines','rule_ids','line_hashes','result_sha256'):
            if original[key] != candidate[key]:
                raise ValueError('Native and Community differ for ' + key)
        if not original['synthetic_movement']:
            if not original['stored_match'] or not candidate['stored_match']:
                raise ValueError('Historical components differ')
            totals.append(original['lines'])
    if (totals != [20,15,19,15,17] or len({r['slip'] for r in originals[:5]}) != 5
            or any(r['synthetic_movement'] for r in originals[:5])
            or not originals[-1]['synthetic_movement'] or originals[-1]['slip'] != originals[0]['slip']):
        raise ValueError('Expected the original October cohort and a separate positive movement')
    for result in candidates:
        conditions = [(i, value) for i, name, value in result['events'] if name == '_satisfy_condition']
        if conditions != [(67,result['synthetic_movement']), (68,result['synthetic_movement']), (8,True), (32,True)]:
            raise ValueError('Duplicate conditions changed')
        expected_results = [67,68,8,32] if result['synthetic_movement'] else [8,32]
        if [i for i, name, _ in result['events'] if name == '_compute_rule'] != expected_results:
            raise ValueError('The engine did not compute both eligible rules')
        if (8 in result['rule_ids'] or 32 not in result['rule_ids'] or 67 in result['rule_ids']
                or (68 in result['rule_ids']) != result['synthetic_movement']):
            raise ValueError('Stored effective rule identity changed')
    return sum(totals)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('native',type=Path)
    parser.add_argument('community',type=Path)
    args = parser.parse_args()
    total = match(json.loads(args.native.read_bytes()), json.loads(args.community.read_bytes()))
    print(f'Five historical drafts, {total} stored lines and one positive movement matched')


if __name__ == '__main__':
    main()
