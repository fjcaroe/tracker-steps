"""Use the explicit native user/employee link, never a display-name match.
Run as postgres against the private review copy before Development. Production
driver rows and the native employee master are never modified.
"""
import argparse,json
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('database');parser.add_argument('plan',type=Path);args=parser.parse_args()
assert args.database=='tracker_steps_development' or args.database.startswith('PERSONAL_JOURNEY_QA_')
plan=json.loads(args.plan.read_text())
with psycopg2.connect(dbname='LAB_TAREAS',cursor_factory=RealDictCursor) as native:
 native.set_session(readonly=True)
 with native.cursor() as cur:
  cur.execute('SELECT name,identification_id,user_id,company_id FROM hr_employee WHERE id=%s AND active',(plan['employee_id'],));employee=cur.fetchone()
  assert employee and employee['user_id']==plan['user_id'] and employee['company_id']==plan['company_id']
with psycopg2.connect(dbname=args.database,cursor_factory=RealDictCursor) as db:
 with db.cursor() as cur:
  cur.execute('SELECT count(*) n FROM tracking_sessions WHERE driver_id=%s',(plan['driver_id'],));assert cur.fetchone()['n']==0,'Existing driver history requires explicit identity reconciliation'
  cur.execute('SELECT * FROM drivers WHERE id=%s FOR UPDATE',(plan['driver_id'],));old=cur.fetchone();assert old and old['is_active']
  external='LAB_TAREAS:hr.employee:'+str(plan['employee_id']);assert old['external_id'] in (None,external)
  cur.execute('UPDATE drivers SET name=%s,rut=%s,external_id=%s WHERE id=%s',(employee['name'],employee['identification_id'],external,plan['driver_id']))
print('PERSONAL_DRIVER_ALIGNED native_user_relation=True production_driver_unchanged=True')
