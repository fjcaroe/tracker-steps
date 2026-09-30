"""Exercise new association lifecycle on a restored QA PostgreSQL database only."""
import os, sys
name = sys.argv[1]
assert name.startswith('TRACKER_CONFIG_QA_')
os.environ['DATABASE_URL'] = 'postgresql+psycopg2:///'+name
os.environ['JWT_SECRET'] = 'qa-only-local-process'
from app.main import app
from app.db.session import SessionLocal
from app.models.fleet import Tenant, Asset, Position, Assignment, now
from app.routers.fleet_configuration import register, associate, inventory, RegisterDevice, AssociateDevice
with SessionLocal() as db:
    db.add(Tenant(id='qa-tenant',issuer='qa-config',company_id=1,name='QA'))
    db.flush()
    db.add_all([Asset(id='qa-car1',tenant_id='qa-tenant',source_id='qa1',name='QA One'),
                Asset(id='qa-car2',tenant_id='qa-tenant',source_id='qa2',name='QA Two')])
    db.commit()
    ctx={'tenant_id':'qa-tenant','role':'manager','user_id':'qa'}
    rid=register(RegisterDevice(imei='000000000000001',brand='QA',model='QA'),ctx,db)['id']
    associate(rid,AssociateDevice(asset_id='qa-car1',reason='QA assignment',version=1),ctx,db)
    item=inventory(db,ctx)['items'][0]
    assert item['asset_id']=='qa-car1' and item['tracking_approved'] is False
    assignment=db.query(Assignment).filter_by(asset_id='qa-car1',valid_to=None).one()
    db.add(Position(tenant_id='qa-tenant',device_id=item['device_id'],asset_id='qa-car1',
                    assignment_id=assignment.id,source_id='qa-event',recorded_at=now(),lat=-33,lon=-70,quality='gps'))
    db.commit()
    associate(rid,AssociateDevice(asset_id='qa-car2',reason='QA reassignment',version=2),ctx,db)
    assert db.query(Position).filter_by(asset_id='qa-car1').count()==1
    assert db.query(Assignment).filter_by(device_id=item['device_id'],valid_to=None).one().asset_id=='qa-car2'
    associate(rid,AssociateDevice(asset_id=None,reason='QA detach',version=3),ctx,db)
    assert inventory(db,ctx)['items'][0]['asset_id'] is None
print('POSTGRES_CONFIGURATION_LIFECYCLE_OK')
