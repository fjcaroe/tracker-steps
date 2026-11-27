"""Compare every stored table in the original Steps CRM restore with its Community copy."""
import argparse
from contextlib import closing
import fcntl
import json
import os
from pathlib import Path
import re

import psycopg2

from compare_sys_full_restore import snapshot
from prepare_steps_crm_cohort import digest, SOURCE_INVENTORY, SOURCE_MANIFESTS
from restore_sys_previred_pair import LOCK, require


def modules(database):
    with closing(psycopg2.connect(dbname=database, user='postgres', host='/var/run/postgresql')) as conn:
        conn.set_session(readonly=True, isolation_level='REPEATABLE READ')
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL TIME ZONE 'UTC'")
            cursor.execute("""
                SELECT name,state,latest_version,license,
                       encode(sha256(convert_to((to_jsonb(m)-'state')::text,'UTF8')),'hex')
                FROM ir_module_module m ORDER BY name
            """)
            return {name: (state, version, license_name, row_hash)
                    for name, state, version, license_name, row_hash in cursor.fetchall()}


def compare(native, community, plan):
    expected = set(plan['enabled'])
    require(plan['database'] == community and plan['original'] == 310
            and plan['source_manifest_sha256'] == SOURCE_MANIFESTS and len(expected) == 157,
            'expected-verified-steps-plan')
    before, after = modules(native), modules(community)
    active = [(name, row[1], row[2]) for name, row in before.items() if row[0] == 'installed']
    native_inventory = digest(active)
    require(native_inventory == SOURCE_INVENTORY, 'original-module-inventory-differs')
    # The first selection stored only the manifest digest. Always establish the inventory from the native rows.
    if 'source_inventory_sha256' in plan:
        require(plan['source_inventory_sha256'] == native_inventory, 'plan-inventory-differs')
    excluded = {name for name, _, _ in active} - expected
    require(excluded == set(plan['excluded']) and len(excluded) == 153 and
            all(name in before and before[name][0] == 'installed' for name in expected),
            'original-steps-selection-differs')
    unexpected_modules = sorted(name for name in before.keys() | after.keys()
                                if name not in before or name not in after or
                                after[name] != (('uninstalled' if name in excluded else before[name][0]),
                                                *before[name][1:]))
    required = ('crm_lead', 'res_partner', 'ir_attachment')
    reference, candidate = (snapshot(db, required_nonempty=required) for db in (native, community))
    differences = {section: sorted(key for key in values.keys() | candidate[section].keys()
                                   if values.get(key) != candidate[section].get(key))
                   for section, values in reference.items()}
    expected_tables = differences['public_tables'] == ['ir_module_module'] and not unexpected_modules
    schema_matches = all(not changed for name, changed in differences.items()
                         if name not in ('public_tables', 'sequence_values'))
    return {'original': native, 'community': community, 'source_inventory_sha256': SOURCE_INVENTORY,
            'manifest_sha256': SOURCE_MANIFESTS, 'active': len(expected), 'excluded': len(excluded),
            'module_rows': len(before), 'unexpected_modules': unexpected_modules,
            'counts': {name: len(values) for name, values in reference.items()},
            'rows': sum(count for count, _ in reference['public_tables'].values()),
            'differences': differences, 'preserved_tables_and_schema': expected_tables and schema_matches,
            'preserved_counters': not differences['sequence_values']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suffix', required=True)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    require(re.fullmatch(r'[A-Z0-9_]{1,32}', args.suffix), 'use-private-steps-restores')
    native = 'MANAGEMENT_QA_STEPS_CRM_' + args.suffix
    community = 'COMMUNITY_STEPS_CRM_' + args.suffix
    os.umask(0o077)
    with open(LOCK, 'rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        report = compare(native, community, json.loads(args.plan.read_bytes()))
        with args.output.open('x', encoding='utf-8') as out:
            json.dump(report, out, indent=2)
    print(json.dumps(report['counts']), flush=True)
    require(report['preserved_tables_and_schema'], 'table-or-schema-drift')
    require(report['preserved_counters'], 'sequence-state-drift')


if __name__ == '__main__':
    main()
