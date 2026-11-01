"""Real Coban TCP -> private target-copy API -> mobile's read-only snapshot."""
import json
import os
from pathlib import Path
import sys


def main():
 assert os.environ['DATABASE_URL'].rsplit('/',1)[-1].startswith('COBAN_QA_')
 from receivers.coban.rehearse import main as receive
 from app.main import app  # Register the full production model graph before querying ORM relations.
 from app.db.session import SessionLocal
 from app.models.sessions import TrackingSession
 with SessionLocal() as db:before=db.query(TrackingSession).count()
 receive()
 from app.models.fleet import Tenant,Asset,Device,Assignment,now
 from app.routers.fleet import asset_out
 with SessionLocal() as db:
  assert db.query(TrackingSession).count()==before,'Hardware reception must not create a journey'
  tenant=db.query(Tenant).filter_by(issuer='CERRO_EL_PLOMO',company_id=2).one()
  device=db.query(Device).filter_by(imei='000000000000001').one()
  assignment=db.query(Assignment).filter_by(device_id=device.id,valid_to=None).one()
  asset=db.get(Asset,assignment.asset_id)
  item=asset_out(db,asset,now());assert item['last_position']['lat']==-33 and item['last_position']['lon']==-70
  snapshot={'tenant':tenant.name,'tenant_id':tenant.id,'user_id':'qa-viewer','role':'viewer','items':[item],'total':1,'next_cursor':None,'generated_at':now()}
  Path(sys.argv[1]).write_text(json.dumps(snapshot,default=lambda value:value.isoformat()))
 print('MOBILE_HARDWARE_COPY_OK tcp=True fleet_projection=True no_journey_created=True')


if __name__=='__main__':main()
