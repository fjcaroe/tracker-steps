"""Real API flow on the already-onboarded private destination copy; rollback."""
import json,os,uuid
from datetime import datetime,timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.db.session import engine,get_db
from app.core.security import get_current_user
from app.models.users import User
from app.models.work_orders import WorkOrder
from app.models.sessions import TrackingSession
assert engine.url.database.startswith('PERSONAL_JOURNEY_QA_')
ids=json.loads(os.environ['JOURNEY_QA_IDS'])
with engine.connect() as connection:
 outer=connection.begin()
 try:
  def database():
   with Session(bind=connection,join_transaction_mode='create_savepoint') as db:yield db
  def current():
   with Session(bind=connection) as db:return db.query(User).filter_by(is_active=True,is_admin=True).first()
  app.dependency_overrides[get_db]=database;app.dependency_overrides[get_current_user]=current
  client=TestClient(app);now=datetime.now(timezone.utc).isoformat()
  machines=client.get('/machines').json();assert len(machines)==1 and machines[0]['id']==ids['machine_id'] and machines[0]['passenger_capacity']==4 and machines[0]['fuel_consumption_unit']=='kmpl'
  body=dict(code='PRIVATE-JOURNEY-'+uuid.uuid4().hex,work_date=now[:10],season=now[:4],machine_id=ids['machine_id'],activity_id=ids['activity_id'],labor_id=ids['labor_id'],cost_center_id=ids['cost_center_id'],hourmeter_initial=None,fuel_tank_start_liters=None)
  response=client.post('/work_orders',json=body);assert response.status_code==200,response.text;wo=response.json()['id']
  session=str(uuid.uuid4());response=client.post('/sessions/start',json=dict(id=session,machine_id=ids['machine_id'],driver_id=ids['driver_id'],cost_center_id=ids['cost_center_id'],work_order_id=wo,started_at=now));assert response.status_code==200,response.text
  assert client.post('/sessions/'+session+'/close').status_code==200
  assert client.put('/work_orders/'+str(wo),json=dict(hourmeter_final=None,fuel_tank_end_liters=None,fuel_refill_liters=None)).status_code==200
  with Session(bind=connection) as db:
   order=db.get(WorkOrder,wo);assert order.hourmeter_initial is None and order.hourmeter_final is None and order.fuel_tank_start_liters is None and order.fuel_tank_end_liters is None
  print('PERSONAL_JOURNEY_API_OK single_real_car=True start_close=True unknown_readings_null=True capacity=4')
 finally:app.dependency_overrides.clear();outer.rollback()
