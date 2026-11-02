"""Exercise scoped GPS requests on a fresh private PostgreSQL destination copy."""
import json, os, uuid
import dotenv
# Frontend build files may contain private configuration. Copy QA supplies every
# backend setting explicitly and must not discover or read those files.
dotenv.load_dotenv=lambda *args, **kwargs: False
from pathlib import Path
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.main import app
from app.models.fleet import Tenant, Asset, now

assert os.environ['DATABASE_URL'].split('/')[-1].startswith('TRACKER_ACCESS_GPS_QA_')
facts=json.loads(Path(os.environ['TRACKER_ACCESS_FACTS']).read_text())
engine=create_engine(os.environ['DATABASE_URL'])
with Session(engine) as db:
 tenant=db.query(Tenant).filter_by(issuer='CERRO_EL_PLOMO',company_id=facts['company_id']).one()
 allowed=db.query(Asset).filter_by(id=facts['asset_id'],tenant_id=tenant.id).one()
 hidden=Asset(id=str(uuid.uuid4()),tenant_id=tenant.id,source_id='private-copy-only',name='QA hidden')
 db.add(hidden);db.commit();hidden_id=hidden.id
os.environ['TRACKER_BRIDGE_KEYS']=json.dumps({'CERRO_EL_PLOMO':'copy-only-key'})
def auth(ids=None, role='operator'):
 t=int(now().timestamp());claims=dict(iss='CERRO_EL_PLOMO',aud='steps-tracker-v1',sub='copy-operator',iat=t,exp=t+60,role=role,company_id=facts['company_id'],manage_protection=True)
 if ids is not None:claims['asset_ids']=ids
 return {'Authorization':'Bearer '+jwt.encode(claims,'copy-only-key',algorithm='HS256')}
c=TestClient(app);h=auth([facts['asset_id']]);snapshot=c.get('/v1/fleet/snapshot',headers=h).json()
assert snapshot['total']==1 and snapshot['items'][0]['asset_id']==facts['asset_id']
assert c.get('/v1/assets/'+hidden_id,headers=h).status_code==404
assert c.get('/v1/assets/'+hidden_id+'/positions',headers=h).status_code==404
assert c.get('/v1/assets/'+facts['asset_id']+'/positions',headers=h).status_code==200
assert c.get('/v1/fleet/snapshot',headers=auth([])).json()['total']==0
assert c.get('/v1/fleet/snapshot',headers=auth(role='manager')).json()['total']>=2
assert c.get('/v1/configuration',headers=h).status_code==403
assert c.post('/v1/classic-session',headers=h,json={'login':'copy-only','name':'Copy'}).status_code==403
print('TRACKER_ACCESS_GPS_COPY_OK scoped_snapshot=True guessed_ids_denied=True manager_full=True')
