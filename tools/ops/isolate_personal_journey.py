"""Install a Development-only classic Tracker database from schema + explicit rows.

No production GPS data is copied. JWT/native login identity keeps the existing
Tracker user ID. The hardware fleet continues through the existing Odoo bridge.
"""
import argparse,fcntl,json,os,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import urlopen,Request
import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
from dotenv import dotenv_values
from sqlalchemy.engine import make_url
from jose import jwt
API=Path('/opt/fernando_odoo18/apis/backend/tracker_py');UNIT=Path('/etc/systemd/system/steps-tracker-dev-api.service');ENV=Path('/etc/steps-tracker-development.env');TARGET='tracker_steps_development'
def run(*cmd,**kw):return subprocess.run(list(map(str,cmd)),check=True,**kw)
def rows(db,table,key,value):
 with db.cursor(cursor_factory=RealDictCursor) as cur:
  cur.execute(sql.SQL('SELECT * FROM {} WHERE {}=%s').format(sql.Identifier(table),sql.Identifier(key)),(value,));return list(cur.fetchall())
def insert(db,table,values):
 with db.cursor() as cur:
  for row in values:
   cur.execute(sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(sql.Identifier(table),sql.SQL(',').join(map(sql.Identifier,row)),sql.SQL(',').join(sql.Placeholder() for _ in row)),list(row.values()))
def create_schema(name,role,schema):
 run('sudo','-u','postgres','createdb','-O',role,name)
 with schema.open('rb') as inp:run('sudo','-u','postgres','pg_restore','--no-owner','--no-acl','--role',role,'-d',name,stdin=inp)
 with psycopg2.connect(dbname='postgres') as db:
  with db.cursor() as cur:cur.execute(sql.SQL('REVOKE CONNECT ON DATABASE {} FROM PUBLIC').format(sql.Identifier(name)))
def wait_api(token):
 for _ in range(50):
  try:
   with urlopen(Request('http://127.0.0.1:8012/machines',headers={'Authorization':'Bearer '+token}),timeout=2) as response:
    result=json.load(response)
    if len(result)==1 and result[0]['passenger_capacity']==4:return
  except OSError:pass
  time.sleep(.3)
 raise RuntimeError('Dedicated Development database did not verify')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['qa','apply']);p.add_argument('source',type=Path);p.add_argument('plan',type=Path);p.add_argument('ids',type=Path);p.add_argument('root',type=Path);a=p.parse_args();assert os.geteuid()==0
 os.umask(0o077);a.root.mkdir(parents=True,exist_ok=True);plan=json.loads(a.plan.read_text());ids=json.loads(a.ids.read_text())
 values=dotenv_values(API/'.env');url=make_url(values['DATABASE_URL']);role=url.username;assert url.database=='tracker_steps' and role
 with open('/run/lock/steps-environments.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  with psycopg2.connect(dbname='tracker_steps') as source:
   source.set_session(readonly=True)
   with source.cursor(cursor_factory=RealDictCursor) as cur:
    cur.execute("SELECT id FROM gps_tenants WHERE issuer='LAB_TAREAS' AND company_id=%s",(plan['company_id'],));tenant=cur.fetchone()['id']
   users=rows(source,'users','username','odoo-'+tenant.replace('-','')[:8]+'-'+str(plan['user_id']));assert len(users)==1 and users[0]['is_active'] and users[0]['is_admin']
   data={'users':users,'activities':rows(source,'activities','id',ids['activity_id']),'cost_centers':rows(source,'cost_centers','id',ids['cost_center_id']),'drivers':rows(source,'drivers','id',ids['driver_id']),'labors':rows(source,'labors','id',ids['labor_id']),'machines':rows(source,'machines','id',ids['machine_id'])}
   assert len(data['machines'])==1 and data['machines'][0]['external_id']==plan['machine_external_id']
   with source.cursor() as cur:
    for table in ('tracking_sessions','work_orders','mobile_routes'):
     cur.execute('SELECT count(*) FROM '+table+' WHERE machine_id=%s',(ids['machine_id'],));assert cur.fetchone()[0]==0,'A real journey already exists; preserve and migrate its lineage explicitly'
  stamp=datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S');stage=a.root/(a.action+'-'+stamp);stage.mkdir(mode=0o700)
  schema=stage/'schema.dump'
  with schema.open('wb') as out:run('sudo','-u','postgres','pg_dump','-Fc','--schema-only','tracker_steps',stdout=out)
  target='PERSONAL_JOURNEY_QA_SPLIT_'+stamp if a.action=='qa' else TARGET
  create_schema(target,role,schema)
  with psycopg2.connect(dbname=target) as db:
   for table,records in data.items():insert(db,table,records)
   insert(db,'user_cost_centers',[dict(user_id=users[0]['id'],cost_center_id=ids['cost_center_id'])])
   with db.cursor() as cur:
    for table in data:
     cur.execute(sql.SQL("SELECT setval(pg_get_serial_sequence(%s,'id'),(SELECT max(id) FROM {}),true)").format(sql.Identifier(table)),(table,))
    for table in ('gps_assets','gps_devices','gps_positions'):
     cur.execute('SELECT count(*) FROM '+table);assert cur.fetchone()[0]==0,'Production hardware data must not enter the Development classic database'
  if a.action=='qa':
   try:
    with (stage/'functional.log').open('wb') as log:run('sudo','-u','postgres','env','DATABASE_URL=postgresql+psycopg2:///'+target,'JWT_SECRET=private-journey-copy-only','JOURNEY_QA_IDS='+json.dumps(ids),'PYTHONPATH='+str(a.source/'backend/tracker_py')+':/opt/steps-validation/personal-transfer-test-deps',API/'.venv/bin/python',a.source/'tools/qa/tracker/rehearse_personal_journey.py',stdout=log,stderr=subprocess.STDOUT)
    assert 'PERSONAL_JOURNEY_API_OK' in (stage/'functional.log').read_text();(a.root/'qa.json').write_text(json.dumps(dict(ids=ids,isolated=True,native_login_id=users[0]['id'])));print('PERSONAL_JOURNEY_ISOLATED_QA_OK no_hardware_copied=True')
   finally:run('sudo','-u','postgres','dropdb','--if-exists',target)
   return
  assert json.loads((a.root/'qa.json').read_text())['ids']==ids
  oldunit=UNIT.read_text();assert 'EnvironmentFile=' not in oldunit and not ENV.exists()
  (stage/'service.backup').write_text(oldunit)
  with (stage/'tracker_steps.dump').open('wb') as out:run('sudo','-u','postgres','pg_dump','-Fc','tracker_steps',stdout=out)
  run('pg_restore','--file=/dev/null',stage/'tracker_steps.dump')
  run('systemctl','stop','steps-tracker-dev-api')
  try:
   with psycopg2.connect(dbname='tracker_steps') as source:
    with source.cursor() as cur:
     cur.execute('DELETE FROM machines WHERE id=%s AND external_id=%s',(ids['machine_id'],plan['machine_external_id']));assert cur.rowcount==1
     cur.execute('DELETE FROM labors WHERE id=%s AND code=%s',(ids['labor_id'],'CONDUCCION'));assert cur.rowcount==1
     cur.execute('DELETE FROM cost_centers WHERE id=%s AND external_id=%s',(ids['cost_center_id'],plan['cc_external_id']));assert cur.rowcount==1
    dburl=url.set(database=TARGET).render_as_string(hide_password=False);assert '\n' not in dburl
    ENV.write_text('DATABASE_URL='+dburl+'\n');ENV.chmod(0o600)
    UNIT.write_text(oldunit.replace('Environment=PYTHONUNBUFFERED=1','Environment=PYTHONUNBUFFERED=1\nEnvironmentFile=/etc/steps-tracker-development.env'))
    run('systemctl','daemon-reload');run('systemctl','start','steps-tracker-dev-api')
    token=jwt.encode({'sub':str(users[0]['id']),'exp':int(time.time())+300},values['JWT_SECRET'],algorithm='HS256');wait_api(token)
   (a.root/'delivery.json').write_text(json.dumps(dict(database=TARGET,ids=ids,native_login_id=users[0]['id'],backup=str(stage),production_machines=0,hardware_copied=0),indent=2));print('PERSONAL_JOURNEY_DATABASE_ISOLATED production_catalog_unchanged=True hardware_copied=0')
  except Exception:
   UNIT.write_text(oldunit);ENV.unlink(missing_ok=True);run('systemctl','daemon-reload');run('systemctl','restart','steps-tracker-dev-api');raise
if __name__=='__main__':main()
