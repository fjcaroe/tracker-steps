"""Verify persistence, report math and conflict handling on a restored QA DB."""
import os, sys
from datetime import timedelta
from fastapi import HTTPException
name=sys.argv[1]
assert name.startswith('TRACKER_ZONES_QA_')
os.environ['DATABASE_URL']='postgresql+psycopg2:///'+name
os.environ['JWT_SECRET']='qa-only-local-process'
from app.main import app
from app.db.session import SessionLocal
from app.models.fleet import Tenant, Asset, Device, Assignment, Position, now
from app.routers.zones import create, update, report, ZoneInput, ZoneUpdate

with SessionLocal() as db:
    db.add(Tenant(id='qa-zone-tenant',issuer='qa-zones',company_id=1,name='QA zones'))
    db.flush()
    db.add(Asset(id='qa-zone-asset',tenant_id='qa-zone-tenant',source_id='qa-zone',name='QA vehicle'))
    db.add(Device(id='qa-zone-device',imei='000000000000002',brand='QA',model='QA'))
    db.flush()
    start=now()-timedelta(hours=1)
    db.add(Assignment(id='qa-zone-assignment',tenant_id='qa-zone-tenant',device_id='qa-zone-device',asset_id='qa-zone-asset',valid_from=start))
    db.flush()
    for i,lon in enumerate([-.001,.003]):
        db.add(Position(tenant_id='qa-zone-tenant',asset_id='qa-zone-asset',device_id='qa-zone-device',assignment_id='qa-zone-assignment',source_id='qa-zone-'+str(i),recorded_at=start+timedelta(seconds=i*120),lat=.001,lon=lon,speed_kmh=10,quality='gps'))
    db.commit()
    ctx={'tenant_id':'qa-zone-tenant','role':'manager','user_id':'qa'}
    body=dict(name='QA polygon',vertices=[{'lat':y,'lon':x} for x,y in [(0,0),(.002,0),(.002,.002),(0,.002)]])
    zone=create(ZoneInput(**body),ctx,db)
    result=report(zone['id'],'qa-zone-asset',start,start+timedelta(seconds=120),ctx,db)
    assert result['entries']==result['exits']==1
    assert abs(result['inside']['seconds']-60)<.001 and result['coverage_pct']==100
    changed=update(zone['id'],ZoneUpdate(**body,version=1,active=False),ctx,db)
    assert changed['version']==2 and not changed['active']
    try:update(zone['id'],ZoneUpdate(**body,version=1),ctx,db)
    except HTTPException as e:assert e.status_code==409
    else:raise AssertionError('Version conflict not enforced')
print('POSTGRES_ZONES_LIFECYCLE_AND_REPORT_OK')
