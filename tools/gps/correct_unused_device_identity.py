"""Correct a confirmed one-digit IMEI typo on an unused capture-only registration.

Root operation on odoo-new. Private JSON input and receipts stay outside Git.
Keeps the device/registration IDs, SIM, audit history and capture mode. Refuses
assigned, approved or contacted devices, collisions, stale rows and telemetry.
The exact transaction is rehearsed in a fresh private copy before production.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

PYTHON = '/opt/fernando_odoo18/apis/backend/tracker_py/.venv/bin/python'


def valid_imei(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{15}', value):
        return False
    digits = [int(v) for v in value]
    return sum(v if i % 2 == 0 else (2*v if v < 5 else 2*v-9) for i,v in enumerate(digits)) % 10 == 0


def transaction(database, payload):
    import psycopg2
    from psycopg2.extras import Json
    plan = payload['plan']
    assert database == 'tracker_steps' or database.startswith('COBAN_ID_QA_')
    assert re.fullmatch(r'\d{15}', plan['old_imei']) and valid_imei(plan['new_imei'])
    assert sum(a != b for a,b in zip(plan['old_imei'],plan['new_imei'])) == 1
    assert len(plan['reason'].strip()) >= 10
    with psycopg2.connect(dbname=database, options='-c lock_timeout=5s -c statement_timeout=15s') as db:
        with db.cursor() as cr:
            cr.execute('SELECT id FROM gps_tenants WHERE issuer=%s AND company_id=%s AND name=%s', (plan['issuer'],plan['company_id'],plan['company_name']))
            tenant = cr.fetchone(); assert tenant, 'Company identity mismatch'
            cr.execute('SELECT row_to_json(r),row_to_json(d) FROM gps_device_registrations r JOIN gps_devices d ON d.id=r.device_id WHERE d.imei=%s AND r.tenant_id=%s FOR UPDATE OF r,d', (plan['old_imei'],tenant[0]))
            rows = cr.fetchall(); assert len(rows)==1, 'Expected exactly one existing registration'
            registration, device = rows[0]
            assert registration['phone']==plan['phone'], 'SIM mismatch'
            assert registration['receiver_mode']=='capture' and not device['tracking_approved'], 'Not an unused capture registration'
            assert registration['receiver_seen_at'] is None and registration['receiver_fix_at'] is None and not registration['receiver_pending'], 'Contacted device requires another workflow'
            for table in ('gps_assignments','gps_positions'):
                cr.execute(f'SELECT count(*) FROM {table} WHERE device_id=%s',(device['id'],)); assert cr.fetchone()[0]==0, 'History must not be relabelled'
            cr.execute('SELECT count(*) FROM gps_devices WHERE imei=%s',(plan['new_imei'],)); assert cr.fetchone()[0]==0, 'New identity already exists'
            before = {'registration':registration,'device':device}
            if payload['action']=='inspect': return before
            assert before==payload['expected'], 'Concurrent registration change; stop'
            cr.execute('UPDATE gps_devices SET imei=%s WHERE id=%s', (plan['new_imei'],device['id']))
            cr.execute('UPDATE gps_device_registrations SET version=version+1 WHERE id=%s',(registration['id'],))
            detail = {'registration_id':registration['id'],'device_id':device['id'],'previous_imei':plan['old_imei'],'confirmed_imei':plan['new_imei'],'reason':plan['reason']}
            cr.execute('INSERT INTO gps_audit_events(id,tenant_id,actor,action,detail,created_at) VALUES(%s,%s,%s,%s,%s,now())', (str(uuid.uuid4()),tenant[0],'support:codex','device_identity_corrected',Json(detail)))
            cr.execute('SELECT row_to_json(r),row_to_json(d) FROM gps_device_registrations r JOIN gps_devices d ON d.id=r.device_id WHERE r.id=%s',(registration['id'],))
            new_registration,new_device=cr.fetchone()
            assert new_device=={**device,'imei':plan['new_imei']}
            assert new_registration=={**registration,'version':registration['version']+1}
            return {'before':before,'after':{'registration':new_registration,'device':new_device},'preserved_ids':True,'preserved_sim':True,'history_rows':0}


def main():
    if len(sys.argv)==3 and sys.argv[1]=='--worker':
        print(json.dumps(transaction(sys.argv[2],json.load(sys.stdin)))); return
    import fcntl
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path)
    parser.add_argument('--receipts',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args(); assert os.geteuid()==0; os.umask(0o077)
    plan=json.loads(args.input.read_text(encoding='utf-8-sig'))
    def worker(database, action, expected=None):
        payload={'plan':plan,'action':action,'expected':expected}
        result=subprocess.run(['sudo','-u','postgres',PYTHON,str(Path(__file__).resolve()),'--worker',database],input=json.dumps(payload),text=True,capture_output=True)
        if result.returncode: raise RuntimeError('Identity correction refused; no change from this transaction. '+result.stderr[-500:])
        return json.loads(result.stdout)
    def run(*command,**kwargs):return subprocess.run([str(c) for c in command],check=True,**kwargs)
    with open('/run/lock/steps-environments.lock','a') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX)
        expected=worker('tracker_steps','inspect')
        if not args.apply: print(json.dumps({'eligible':True,'dry_run':True})); return
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        root=args.receipts/stamp; root.mkdir(parents=True,mode=0o700); root.chmod(0o700)
        (root/'before.json').write_text(json.dumps(expected,indent=2))
        dump=root/'tracker_steps.dump'
        with dump.open('wb') as output:run('sudo','-u','postgres','pg_dump','-Fc','tracker_steps',stdout=output)
        run('pg_restore','--file=/dev/null',dump)
        qa='COBAN_ID_QA_'+datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
        run('sudo','-u','postgres','createdb',qa)
        try:
            with dump.open('rb') as source:run('sudo','-u','postgres','pg_restore','--no-owner','--no-acl','-d',qa,stdin=source)
            proof=worker(qa,'apply',expected)
            (root/'qa.json').write_text(json.dumps(proof,indent=2))
        finally:run('sudo','-u','postgres','dropdb','--if-exists',qa)
        applied=worker('tracker_steps','apply',expected)
        assert applied==proof
        (root/'production.json').write_text(json.dumps(applied,indent=2))
        print(json.dumps({'corrected':True,'same_device_and_registration':True,'mode':'capture','fresh_copy_passed':True,'backup_saved':True,'assigned':False}))


if __name__=='__main__': main()
