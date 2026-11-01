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
 from app.models.fleet import Tenant,Asset,Device,DeviceRegistration,Assignment,now
 from app.routers.fleet import asset_out
 with SessionLocal() as db:
  assert db.query(TrackingSession).count()==before,'Hardware reception must not create a journey'
  tenant=db.query(Tenant).filter_by(issuer='CERRO_EL_PLOMO',company_id=2).one()
  device=db.query(Device).filter_by(imei='000000000000001').one()
  assignment=db.query(Assignment).filter_by(device_id=device.id,valid_to=None).one()
  asset=db.get(Asset,assignment.asset_id)
  item=asset_out(db,asset,now());assert item['last_position']['lat']==-33 and item['last_position']['lon']==-70
  # Bench commissioning must be visible before a vehicle is associated. All
  # changes below are confined to the disposable copy's synthetic fixture.
  registration=db.query(DeviceRegistration).filter_by(device_id=device.id).one()
  assignment.valid_to=now();registration.receiver_mode='capture';device.tracking_approved=False;db.commit()
  assert registration.receiver_fix_at and registration.receiver_lat==-33
  diagnostic={'id':registration.id,'label':'GPS · ••••0001','asset_id':None,'asset_name':None,'mode':'capture','last_seen_at':registration.receiver_seen_at,'fix_at':registration.receiver_fix_at,'fix_received_at':registration.receiver_fix_received_at,'lat':registration.receiver_lat,'lon':registration.receiver_lon}
  snapshot={'tenant':tenant.name,'tenant_id':tenant.id,'user_id':'qa-manager','role':'manager','items':[],'total':0,'next_cursor':None,'generated_at':now(),'installations':[diagnostic]}
  Path(sys.argv[1]).write_text(json.dumps(snapshot,default=lambda value:value.isoformat()))
 print('MOBILE_HARDWARE_COPY_OK tcp=True fleet_projection=True no_journey_created=True')


if __name__=='__main__':main()
