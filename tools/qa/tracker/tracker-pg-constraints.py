import psycopg2
from psycopg2 import errors
import os
database = os.environ['TRACKER_QA_DATABASE']
if not database.upper().startswith(('TRACKER_LAYOUT_QA_', 'TRACKER_QA_')):
 raise RuntimeError('Se requiere una base QA independiente')
connection=psycopg2.connect(dbname=database)
try:
 with connection.cursor() as c:
  c.execute("INSERT INTO gps_tenants(id,issuer,company_id,name,timezone,retention_days) VALUES ('qa-t1','qa1',1,'QA1','UTC',30),('qa-t2','qa2',1,'QA2','UTC',30)")
  c.execute("INSERT INTO gps_assets(id,tenant_id,source_id,name,type,created_at) VALUES ('qa-a1','qa-t1','qa1','A','tractor',now()),('qa-a2','qa-t2','qa2','B','tractor',now())")
  c.execute("INSERT INTO gps_devices(id,imei,brand,model,freshness_seconds,tracking_approved) VALUES ('qa-d1','qa-device','Test','Test',300,false)")
  c.execute("INSERT INTO gps_assignments(id,tenant_id,device_id,asset_id,valid_from) VALUES ('qa-as1','qa-t1','qa-d1','qa-a1',now()-interval '1 hour')")
  c.execute('SAVEPOINT overlap')
  try:
   c.execute("INSERT INTO gps_assignments(id,tenant_id,device_id,asset_id,valid_from) VALUES ('qa-as2','qa-t2','qa-d1','qa-a2',now())")
   raise AssertionError('overlap accepted')
  except errors.ExclusionViolation: c.execute('ROLLBACK TO SAVEPOINT overlap')
  c.execute('SAVEPOINT cross_tenant')
  try:
   c.execute("INSERT INTO gps_assignments(id,tenant_id,device_id,asset_id,valid_from,valid_to) VALUES ('qa-as3','qa-t1','qa-d1','qa-a2',now()-interval '3 hours',now()-interval '2 hours')")
   raise AssertionError('cross tenant accepted')
  except errors.ForeignKeyViolation: c.execute('ROLLBACK TO SAVEPOINT cross_tenant')
 print('POSTGRES_ASSIGNMENT_CONSTRAINTS_OK')
finally:
 connection.rollback();connection.close()
