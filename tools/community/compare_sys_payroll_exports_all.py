"""Compare full private export receipts and print an aggregate activity report."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def changes(left, right, path=''):
    if isinstance(left, dict) and isinstance(right, dict):
        result = []
        for key in sorted(left.keys() | right.keys()):
            part = f'{path}.{key}' if path else key
            if key not in left or key not in right:
                result.append(part)
            else:
                result.extend(changes(left[key], right[key], part))
        return result
    if path.endswith('by_column') and isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
        return [f'{path}[{i}]' for i,(a,b) in enumerate(zip(left,right),1) if a != b]
    return [] if left == right else [path]


def index(receipt):
    companies = {entry['company']:entry for entry in receipt['latest']}
    if len(companies) != len(receipt['latest']) or not receipt['originals_preserved']:
        raise ValueError('Invalid company census or original-state preservation')
    cases = {}
    for company, group in companies.items():
        for actor in group['operators']:
            ident = company, actor['uid']
            if actor['uid'] <= 1 or ident in cases:
                raise ValueError('User identity is privileged or repeated in private receipt')
            cases[ident] = actor
    return companies, cases


def compare(native, community):
    if native['database'] != 'MANAGEMENT_QA_SYS_PREVIRED_20261126U40N' or native['enterprise'] <= 0:
        raise ValueError('Expected the restored original SyS database')
    if community['database'] != 'COMMUNITY_SYS_PREVIRED_COHORT_20261126U40I' or community['enterprise']:
        raise ValueError('Expected the integrated Community database')
    original, actors = index(native)
    candidate, other = index(community)
    if original.keys() != candidate.keys() or actors.keys() != other.keys() or len(original) != 12:
        raise ValueError('Different company or authenticated operator census')
    if len(actors) != 24 or any(len(record['operators']) != 2 for record in original.values()):
        raise ValueError('Expected the two original active internal operators for every closed company')
    periods = Counter()
    kinds = ('previred','book')
    receipts = {kind:{'matched':0,'native':Counter(),'community':Counter()} for kind in kinds}
    by_company = []
    for cid, group in sorted(original.items()):
        facts = {key: group[key] for key in ('period','closed','closed_ids')}
        if any(value != candidate[cid][key] for key,value in facts.items()):
            raise ValueError('Different closed original record identities or periods')
        periods[group['period']] += group['closed']
        row = {'company':cid, 'period':group['period'], 'closed':group['closed'], 'actors':[]}
        for (company,uid), actor in sorted(actors.items()):
            if company != cid:
                continue
            item = {'uid':uid}
            for kind in kinds:
                one, two = actor[kind], other[(cid,uid)][kind]
                differences = changes(one,two)
                agg = receipts[kind]
                agg['matched'] += int(not differences)
                agg['native'][one['status']] += 1
                agg['community'][two['status']] += 1
                item[kind] = {'native':one['status'],'community':two['status'],'differences':differences}
                if 'file' in one:
                    item[kind].update(rows=one['file']['rows'],columns=one['file']['columns'])
                if kind == 'previred':
                    item[kind].update(issues=one.get('issues',{}), source_records=one.get('mapped_source_slips'),
                                      omissions=one.get('missing_source_count'))
                else:
                    item[kind].update(identity_matches=one.get('identity_matches'),
                                      omissions=one.get('omitted_identities'), extras=one.get('extra_identities'))
            row['actors'].append(item)
        by_company.append(row)
    if periods != {'2026-07-01':3,'2026-10-01':130}:
        raise ValueError('Unexpected original historical input')
    return {'companies':len(original),'operator_company_pairs':len(actors),'closed_by_period':periods,
            'results':receipts,'companies_detail':by_company,'complete_match':all(
                receipts[kind]['matched']==len(actors) for kind in kinds)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('native','community','output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    source, target = args.native.read_bytes(), args.community.read_bytes()
    result = compare(json.loads(source), json.loads(target))
    result.update(native_sha256=hashlib.sha256(source).hexdigest(),community_sha256=hashlib.sha256(target).hexdigest())
    with args.output.open('x', encoding='utf8') as fp:
        json.dump(result,fp,indent=2,sort_keys=True)
    print(json.dumps({k:v for k,v in result.items() if k!='companies_detail'},indent=2))
