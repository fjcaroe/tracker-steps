"""Restore the validated three-column estimate constraint in the private Cerro library."""
import argparse
import fcntl
import hashlib
import json

import psycopg2

SOURCE = 'MANAGEMENT_QA_CERRO_PAYROLL_API_ORIGINAL_HANDOVER_20261126U40D'
TARGET = 'COMMUNITY_LIBRARY_CERRO_20261126U41L'
ESTIMATE_TARGET = 'COMMUNITY_CERRO_BOM_ESTIMATE_20261126U42E'
NAME = 'step_management_estimation_line_estimation_line_center_unique'
DEFINITION = 'UNIQUE (estimation_id, center_id, cuartel_id)'


def evidence(cr):
    cr.execute("""SELECT pg_get_constraintdef(oid),convalidated FROM pg_constraint
                  WHERE conrelid='step_management_estimation_line'::regclass AND conname=%s""", [NAME])
    constraint = cr.fetchone()
    cr.execute("""SELECT m.name,c.definition,c.id FROM ir_model_constraint c JOIN ir_module_module m
                  ON m.id=c.module WHERE c.name=%s ORDER BY m.name""", [NAME])
    owners = cr.fetchall()
    cr.execute('SELECT to_jsonb(t)::text FROM step_management_estimation_line t ORDER BY id')
    values = cr.fetchall()
    sha = hashlib.sha256()
    for (value,) in values:
        encoded = value.encode()
        sha.update(len(encoded).to_bytes(8, 'big') + encoded)
    return {'constraint': constraint, 'owners': owners, 'count': len(values), 'rows_sha256': sha.hexdigest()}


def constraints(cr):
    cr.execute("""SELECT c.conrelid::regclass::text,c.conname,c.contype,pg_get_constraintdef(c.oid),c.convalidated
                  FROM pg_constraint c WHERE c.connamespace='public'::regnamespace""")
    return set(cr.fetchall())


def repair(database=TARGET):
    if database not in (TARGET, ESTIMATE_TARGET):
        raise ValueError('Unknown private Cerro copy')
    with psycopg2.connect(dbname=SOURCE, host='/var/run/postgresql') as source, source.cursor() as cr:
        cr.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        original = evidence(cr)
        original_constraints = constraints(cr)
        assert original['constraint'] == (DEFINITION, True)
    with psycopg2.connect(dbname=database, host='/var/run/postgresql') as target, target.cursor() as cr:
        cr.execute("SELECT current_database(),current_user")
        assert cr.fetchone() == (database, 'postgres')
        cr.execute('LOCK TABLE step_management_estimation_line IN ACCESS EXCLUSIVE MODE')
        before = evidence(cr)
        assert {k: v for k, v in before.items() if k != 'constraint'} == {
            k: v for k, v in original.items() if k != 'constraint'}
        if before['constraint'] is None:
            cr.execute("""SELECT 1 FROM step_management_estimation_line
                          WHERE estimation_id IS NOT NULL AND center_id IS NOT NULL AND cuartel_id IS NOT NULL
                          GROUP BY estimation_id,center_id,cuartel_id HAVING count(*)>1 LIMIT 1""")
            assert cr.fetchone() is None
            cr.execute("""ALTER TABLE step_management_estimation_line ADD CONSTRAINT
                          step_management_estimation_line_estimation_line_center_unique
                          UNIQUE (estimation_id,center_id,cuartel_id)""")
        after = evidence(cr)
        assert after == original
        current_constraints = constraints(cr)
        missing = original_constraints - current_constraints
        if missing:
            raise ValueError('Original Cerro constraints differ: ' + repr(sorted((r[0], r[1]) for r in missing)))
    return {'source': SOURCE, 'target': database, 'constraint': DEFINITION,
            'original_constraints': len(original_constraints), 'additional_constraints': len(current_constraints - original_constraints),
            'restored': before['constraint'] is None, 'rows': original['count'], 'rows_sha256': original['rows_sha256']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', choices=(TARGET, ESTIMATE_TARGET), default=TARGET)
    args = parser.parse_args()
    with open('/run/lock/steps-environments.lock', 'rb') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        print(json.dumps(repair(args.database), sort_keys=True))
