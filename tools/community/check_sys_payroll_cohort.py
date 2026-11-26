"""Compare the staged SyS payroll cohort to the original source projections."""
import argparse
from contextlib import closing
import fcntl
import json
import os
from pathlib import Path
import re

import psycopg2

from admit_sys_payroll_storage import related_identity
from preflight_original_history_storage import require
from restore_sys_previred_pair import LOCK, SOCKET
from sys_previred_preservation import capture, differences, projection_query


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database', required=True)
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    require(re.fullmatch(r'COMMUNITY_SYS_PREVIRED_COHORT_[A-Z0-9_]{1,32}', args.database),
            'sys-cohort-private-postflight-required')
    baseline = json.loads(args.baseline.read_bytes())
    plan = json.loads(args.plan.read_bytes())
    require(baseline['stage'] == 'reference-restored' and baseline['preserved'] is True
            and plan['database'] == args.database, 'sys-cohort-postflight-identity')
    original = baseline['snapshot']
    xml_guard = plan['protected']['ir_model_data']
    require(xml_guard['rows'] == original['projections']['ir_model_data']['rows']
            and type(xml_guard['max_id']) is int, 'sys-cohort-original-xml-cutoff')
    os.umask(0o077)
    with open(LOCK, 'rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with closing(psycopg2.connect(dbname=args.database, host=SOCKET, user='postgres')) as conn:
            conn.set_session(readonly=True, isolation_level='REPEATABLE READ')
            with conn.cursor() as cr:
                snapshot = capture(cr, args.database, original)
                # Extra module-registration aliases are legitimate only above
                # the allocator's old maximum. Compare each original SQL row.
                cr.execute(projection_query('ir_model_data', original['columns']['ir_model_data']).replace(
                    'FROM public."ir_model_data") original', 'FROM public."ir_model_data" WHERE id<=%s) original'
                ), (xml_guard['max_id'],))
                original_xml = cr.fetchone()[0]
                added_xml_ids = snapshot['projections']['ir_model_data']['rows'] - original_xml['rows']
                snapshot['projections']['ir_model_data'] = original_xml
                drift = differences(original, snapshot)
                ids = related_identity(cr)
                cr.execute("SELECT name,state FROM ir_module_module WHERE name IN ('payroll','payroll_account',"
                           "'step_payroll_oca_api','step_payroll_oca_sys_history','l10n_cl_simpledigital_payroll') "
                           "ORDER BY name")
                states = dict(cr.fetchall())
        result = dict(database=args.database, original_xml=original_xml, added_xml_ids=added_xml_ids,
                      original_projections=len(original['projections']), original_fks=len(original['foreign_keys']),
                      counters=len(original['counters']), differences=drift, source_related_ids=ids,
                      provider_states=states, preserved=not any(drift.values()))
        with args.output.open('x') as stream:
            json.dump(result, stream, indent=2, sort_keys=True)
            stream.write('\n')
        require(result['preserved'], 'sys-cohort-original-storage-drift')


if __name__ == '__main__':
    main()
