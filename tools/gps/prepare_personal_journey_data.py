"""Explicit private plan: remove unused QA GPS projections and prepare real car.
Run as postgres; exact destination copy first. Native vehicle/history untouched.
"""
import argparse,json,hashlib
from datetime import datetime,timezone
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('database');parser.add_argument('plan',type=Path);args=parser.parse_args()
assert args.database=='tracker_steps' or args.database.startswith('PERSONAL_JOURNEY_QA_')
plan=json.loads(args.plan.read_text());asset=plan['asset_id'];retired=[r['id'] for r in plan['retire_assets']]
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()
with psycopg2.connect(dbname=args.database,cursor_factory=RealDictCursor) as db:
 with db.cursor() as cur:
  cur.execute("SELECT id FROM gps_tenants WHERE issuer='LAB_TAREAS' AND company_id=%s",(plan['company_id'],));tenant=cur.fetchone()['id']
  cur.execute('SELECT * FROM gps_assets WHERE tenant_id=%s FOR UPDATE',(tenant,));assets=cur.fetchall()
  assert sorted(r['id'] for r in assets)==sorted(retired+[asset]),'Concurrent asset inventory change'
  for record in plan['retire_assets']:
   found=next(r for r in assets if r['id']==record['id'])
   assert found['source_id']==record['source_id'] and found['name']==record['name'] and found['plate']==record['plate']
  for table in ('gps_positions','gps_assignments','gps_security_incidents'):
   cur.execute('SELECT count(*) n FROM '+table+' WHERE asset_id=ANY(%s)',(retired,));assert cur.fetchone()['n']==0, 'Selected asset acquired real/history data'
  cur.execute('SELECT row_to_json(p) row FROM gps_positions p WHERE asset_id=%s ORDER BY id',(asset,));positions={r['row']['id']:digest(r['row']) for r in cur.fetchall()}
  cur.execute('SELECT row_to_json(a) row FROM gps_assignments a ORDER BY id');assignments=digest(cur.fetchall())
  cur.execute('SELECT row_to_json(r) row FROM gps_device_registrations r ORDER BY id');registrations=cur.fetchall()
  # Receiver timing fields may advance, but this transaction never updates a registry.
  registry_ids=[r['row']['id'] for r in registrations]
  cur.execute('DELETE FROM gps_security_policies WHERE asset_id=ANY(%s)',(retired,))
  cur.execute('DELETE FROM gps_assets WHERE tenant_id=%s AND id=ANY(%s)',(tenant,retired));assert cur.rowcount==len(retired)
  cur.execute("SELECT id FROM machines WHERE external_id=%s OR plate=%s",(plan['machine_external_id'],plan['plate']));assert not cur.fetchall(),'Existing real machine requires reconciliation, not duplication'
  cur.execute('SELECT count(*) n FROM machines');assert cur.fetchone()['n']==0,'Shared legacy inventory changed; preserve others'
  cur.execute('SELECT id FROM cost_centers WHERE external_id=%s',(plan['cc_external_id'],));cc=cur.fetchone()
  if not cc:
   cur.execute('INSERT INTO cost_centers(external_id,name,created_at) VALUES(%s,%s,now()) RETURNING id',(plan['cc_external_id'],plan['cc_name']));cc=cur.fetchone()
  cur.execute('SELECT id FROM activities WHERE id=%s AND is_active',(plan['activity_id'],));assert cur.fetchone()
  cur.execute('SELECT id FROM labors WHERE code=%s AND activity_id=%s',('CONDUCCION',plan['activity_id']));labor=cur.fetchone()
  if not labor:
   cur.execute('INSERT INTO labors(activity_id,name,code,is_active,created_at) VALUES(%s,%s,%s,true,now()) RETURNING id',(plan['activity_id'],'Conducción','CONDUCCION'));labor=cur.fetchone()
  cur.execute('SELECT id,name FROM drivers WHERE id=%s AND is_active',(plan['driver_id'],));driver=cur.fetchone();assert driver and driver['name']==plan['driver_name']
  cur.execute('INSERT INTO machines(external_id,name,plate,cost_center_id,is_active,created_at,passenger_capacity,fuel_consumption_unit,default_activity_id,default_labor_id) VALUES(%s,%s,%s,%s,true,now(),%s,%s,%s,%s) RETURNING id',(plan['machine_external_id'],plan['machine_name'],plan['plate'],cc['id'],plan['passenger_capacity'],'kmpl',plan['activity_id'],labor['id']));machine=cur.fetchone()
  cur.execute('SELECT row_to_json(a) row FROM gps_assignments a ORDER BY id');assert digest(cur.fetchall())==assignments
  cur.execute('SELECT row_to_json(p) row FROM gps_positions p WHERE asset_id=%s ORDER BY id',(asset,));after={r['row']['id']:digest(r['row']) for r in cur.fetchall()};assert all(after.get(k)==v for k,v in positions.items())
  cur.execute('SELECT id FROM gps_device_registrations ORDER BY id');assert [r['id'] for r in cur.fetchall()]==registry_ids
  result=dict(machine_id=machine['id'],cost_center_id=cc['id'],labor_id=labor['id'],activity_id=plan['activity_id'],driver_id=driver['id'],retired_assets=len(retired),protected_positions=len(positions),asset_id=asset)
 print(json.dumps(result))
