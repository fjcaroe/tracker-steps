"""Compare real SyS October TXT, notices and all stored AFP checks on native and Community runtimes."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def receipt(path):
    raw = path.read_bytes()
    tag = b'STEPS_SYS_PREVIRED_RECEIPT '
    values = [json.loads(line[len(tag):]) for line in raw.splitlines() if line.startswith(tag)]
    if len(values) != 1:
        raise ValueError('One completed payroll wizard receipt per private log is required')
    return values[0], hashlib.sha256(raw).hexdigest()


def compare(native_path, community_path):
    native, native_hash = receipt(native_path)
    community, community_hash = receipt(community_path)
    if native['community'] or not community['community'] or native['enterprise_count'] <= 0 or community['enterprise_count']:
        raise ValueError('Reference and candidate must use their respective official runtimes')
    for run in (native, community):
        if not (run['preserved'] and run['rolled_back'] and run['attempted'] == 1):
            raise ValueError('Original payroll or rollback proof missing')
    if community['october_candidates'] != 1 or native['versions'] != community['versions']:
        raise ValueError('Ambiguous October result or addon version drift')
    expected = native['generated']['98']
    received = community['generated']['98']
    if expected != received or native['diagnostics'] != community['diagnostics']:
        raise ValueError('SyS TXT, eligible cohort, financial checks or diagnostic differences')
    facts = {'period': '2026-10-01', 'spec': '98', 'principal': 5, 'eligible': 5, 'closed_cohort': 5,
             'rows': 5, 'fields': 105, 'dropped': 0, 'annexes': 0, 'with_positive_afp': 5,
             'compared_stored_afp': True, 'operator_uid': 2, 'company_id': 37}
    if any(received.get(k) != v for k, v in facts.items()) or not re.fullmatch('[0-9a-f]{64}', received['file_sha256']):
        raise ValueError('Unexpected SyS October source cohort')
    return {'native_receipt_sha256': native_hash, 'community_receipt_sha256': community_hash,
            'file_sha256': received['file_sha256'], 'exact': True, **facts}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', type=Path, required=True)
    parser.add_argument('--community', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.native, args.community), sort_keys=True))
