"""Read-only Tracker inventory; stdout is private evidence, never Git."""
import argparse,json
import psycopg2
from psycopg2.extras import RealDictCursor
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('database');args=parser.parse_args()
assert args.database=='tracker_steps' or args.database.startswith('PERSONAL_JOURNEY_QA_')
with psycopg2.connect(dbname=args.database,cursor_factory=RealDictCursor) as db:
 db.set_session(readonly=True)
 with db.cursor() as cur:
  result={}
  for table in ['machines','activities','labors','drivers','cost_centers','implements','fields','users']:
   cols='id,username,full_name,is_admin,is_active' if table=='users' else '*'
   cur.execute('SELECT '+cols+' FROM '+table+' ORDER BY id');result[table]=cur.fetchall()
  for table in ['tracking_sessions','work_orders','mobile_routes','mobile_passenger_services','mobile_passenger_events']:
   cur.execute("SELECT to_regclass(%s)",(table,))
   if cur.fetchone()['to_regclass']:
    cur.execute('SELECT count(*) AS n FROM '+table);result[table]=cur.fetchone()['n']
  cur.execute("SELECT * FROM gps_tenants WHERE issuer='LAB_TAREAS' AND company_id=1");tenant=cur.fetchone();result['tenant']=tenant
  cur.execute('SELECT a.*, (SELECT count(*) FROM gps_positions p WHERE p.asset_id=a.id) AS positions, (SELECT count(*) FROM gps_assignments r WHERE r.asset_id=a.id) AS assignments FROM gps_assets a WHERE a.tenant_id=%s ORDER BY a.name',(tenant['id'],));result['assets']=cur.fetchall()
 print(json.dumps(result,default=str,ensure_ascii=False,indent=2))
