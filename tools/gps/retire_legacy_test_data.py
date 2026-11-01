"""Retire explicitly confirmed legacy fixtures; never delete the GPS domain.

Run as postgres over its local socket. Prepare a private plan and dump, restore
that dump to TRACKER_CLEAN_QA_*, then execute there before executing on source.
Identifiers and customer rows belong in the private plan, never in this file.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone

import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor


TABLES = ('tracking_points', 'tracking_sessions', 'work_orders', 'machines')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str,
                                     separators=(',', ':')).encode()).hexdigest()


def save(path, value):
    with open(path, 'x', encoding='utf8') as handle:
        os.chmod(path, 0o600)
        json.dump(value, handle, indent=2, sort_keys=True, default=str)


def rows(cur, table, ids=None):
    query = sql.SQL('SELECT row_to_json(t) AS data FROM {} t').format(sql.Identifier(table))
    args = ()
    if ids is not None:
        query += sql.SQL(' JOIN unnest(%s::text[]) selected_ids(id) ON t.id::text=selected_ids.id')
        args = ([str(i) for i in ids],)
    cur.execute(query, args)
    return sorted((r['data'] for r in cur.fetchall()), key=lambda r: str(r['id']))


def selection(cur, machine_ids, work_order_ids):
    machines = rows(cur, 'machines', machine_ids)
    assert len(machines) == len(set(machine_ids)), 'Selected machine missing'
    cur.execute('SELECT id::text,work_order_id FROM tracking_sessions WHERE machine_id=ANY(%s)',
                (machine_ids,))
    sessions = cur.fetchall()
    orders = set(work_order_ids) | {r['work_order_id'] for r in sessions if r['work_order_id']}
    cur.execute('SELECT id FROM work_orders WHERE machine_id=ANY(%s)', (machine_ids,))
    orders |= {r['id'] for r in cur.fetchall()}
    orders = rows(cur, 'work_orders', sorted(orders))
    session_ids = [r['id'] for r in sessions]
    cur.execute('SELECT id::text FROM tracking_points WHERE session_id::text=ANY(%s::text[])',
                (session_ids,))
    ids = {'machines': machine_ids, 'tracking_sessions': session_ids,
           'work_orders': [r['id'] for r in orders],
           'tracking_points': [r['id'] for r in cur.fetchall()]}
    return {t: rows(cur, t, ids[t]) for t in TABLES}


def protect(cur, issuer, plate):
    cur.execute('''SELECT a.id,a.tenant_id FROM gps_assets a JOIN gps_tenants t ON
                   t.id=a.tenant_id WHERE t.issuer=%s AND a.plate=%s''', (issuer, plate))
    assets = cur.fetchall()
    assert len(assets) == 1, 'Protected real vehicle must be unambiguous'
    cur.execute('''SELECT d.id FROM gps_assignments a JOIN gps_devices d ON d.id=a.device_id
                   JOIN gps_device_registrations r ON r.device_id=d.id
                   WHERE a.asset_id=%s AND a.valid_to IS NULL AND d.tracking_approved
                   AND r.receiver_mode='forward' ''', (assets[0]['id'],))
    assert len(cur.fetchall()) == 1, 'Real GPS tracking must remain approved and assigned'
    # Preserve every existing GPS position across the operation; newer fixes are welcome.
    positions = rows(cur, 'gps_positions')
    return {'asset_id': assets[0]['id'], 'positions':
            {p['id']: digest(p) for p in positions}}


def unaffected(cur, selected):
    """Fingerprint all unrelated rows, including other tenants and operational masters."""
    cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
    result = {}
    for table in (r['tablename'] for r in cur.fetchall()):
        if table in ('gps_positions', 'gps_device_registrations', 'gps_tenants'):
            # Receiver telemetry may advance independently; this tool never writes these.
            continue
        cur.execute(sql.SQL('SELECT row_to_json(t) AS data FROM {} t').format(sql.Identifier(table)))
        excluded = {str(r['id']) for r in selected.get(table, [])}
        data = [r['data'] for r in cur.fetchall() if str(r['data'].get('id')) not in excluded]
        result[table] = digest(sorted(data, key=lambda r: json.dumps(r, sort_keys=True)))
    return result


def dump(database, path):
    subprocess.run(['pg_dump', '-Fc', '-f', str(path), database], check=True)
    os.chmod(path, 0o600)
    subprocess.run(['pg_restore', '--list', str(path)], check=True, stdout=subprocess.DEVNULL)
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'execute'])
    parser.add_argument('--database', required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--machine-ids', type=int, nargs='+')
    parser.add_argument('--work-order-ids', type=int, nargs='*', default=[])
    parser.add_argument('--issuer')
    parser.add_argument('--protect-plate')
    parser.add_argument('--dump', type=Path)
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--qa-receipt', type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    source_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with open('/run/lock/steps-environments.lock', 'rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with psycopg2.connect(dbname=args.database, cursor_factory=RealDictCursor) as conn:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL lock_timeout='10s'")
                cur.execute("SET LOCAL statement_timeout='60s'")
                # Block concurrent legacy writes, while live Coban GPS remains available.
                cur.execute('LOCK TABLE machines,work_orders,tracking_sessions,tracking_points IN EXCLUSIVE MODE')
                if args.action == 'prepare':
                    assert args.machine_ids and args.issuer and args.protect_plate and args.dump
                    selected = selection(cur, args.machine_ids, args.work_order_ids)
                    assert all(r.get('plate') != args.protect_plate for r in selected['machines'])
                    plan = {'database': args.database, 'machine_ids': args.machine_ids,
                            'work_order_ids': args.work_order_ids, 'issuer': args.issuer,
                            'protect_plate': args.protect_plate, 'source_sha': source_sha,
                            'selected': selected, 'created_at': datetime.now(timezone.utc).isoformat(),
                            'protected': protect(cur, args.issuer, args.protect_plate)}
                    # pg_dump uses a second connection; ACCESS SHARE is compatible with EXCLUSIVE.
                    plan['dump'] = str(args.dump)
                    plan['dump_sha'] = dump(args.database, args.dump)
                    save(args.plan, plan)
                    print(json.dumps({'planned': {t: len(r) for t, r in selected.items()}}))
                    return
                plan = json.loads(args.plan.read_text())
                assert plan['source_sha'] == source_sha, 'Tool changed after preparation'
                assert args.receipt and not args.receipt.exists()
                qa = args.database.startswith('TRACKER_CLEAN_QA_')
                if not qa:
                    assert args.database == plan['database'] and args.qa_receipt and args.dump
                    proof = json.loads(args.qa_receipt.read_text())
                    assert proof['qa'] and proof['plan_sha'] == digest(plan)
                    assert proof.get('functional_ok'), 'Copy must pass functional API checks'
                    assert datetime.now(timezone.utc).timestamp() - Path(args.qa_receipt).stat().st_mtime < 3600
                selected = selection(cur, plan['machine_ids'], plan['work_order_ids'])
                assert selected == plan['selected'], 'Selected data changed since review; stop'
                protected = protect(cur, plan['issuer'], plan['protect_plate'])
                assert protected['asset_id'] == plan['protected']['asset_id']
                assert all(protected['positions'].get(k) == v for k, v in plan['protected']['positions'].items())
                before = unaffected(cur, selected)
                if not qa:
                    backup_sha = dump(args.database, args.dump)
                else:
                    assert hashlib.sha256(Path(plan['dump']).read_bytes()).hexdigest() == plan['dump_sha']
                    backup_sha = plan['dump_sha']
                for table in TABLES:
                    ids = [str(r['id']) for r in selected[table]]
                    cur.execute(sql.SQL('DELETE FROM {} t USING unnest(%s::text[]) selected_ids(id) WHERE t.id::text=selected_ids.id').format(sql.Identifier(table)), (ids,))
                    assert cur.rowcount == len(ids)
                assert unaffected(cur, {}) == before, 'Unrelated rows changed'
                after = protect(cur, plan['issuer'], plan['protect_plate'])
                assert all(after['positions'].get(k) == v for k, v in protected['positions'].items())
                result = {'qa': qa, 'database': args.database, 'plan_sha': digest(plan),
                          'source_sha': source_sha, 'backup_sha': backup_sha,
                          'removed': {t: len(r) for t, r in selected.items()},
                          'protected_positions_preserved': True,
                          'unrelated_rows_preserved': True}
            conn.commit()
        save(args.receipt, result)
        print(json.dumps(result))


if __name__ == '__main__':
    main()
