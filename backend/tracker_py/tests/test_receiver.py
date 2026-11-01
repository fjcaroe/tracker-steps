"""Commissioning uses existing GPS masters and enforces tenant, roles and live proof."""
import json
import os
from datetime import timedelta
import pytest
from jose import jwt
from test_fleet import fleet
from app.models.fleet import Tenant, DeviceRegistration, Position, now


def auth(role='manager',company=1,issuer='CERRO_EL_PLOMO'):
    stamp=int(now().timestamp())
    return {'Authorization':'Bearer '+jwt.encode({'iss':issuer,'aud':'steps-tracker-v1','sub':'qa','role':role,'company_id':company,'iat':stamp,'exp':stamp+60},'qa-only-key',algorithm='HS256')}


@pytest.fixture
def setup(fleet):
    client,factory=fleet
    os.environ['TRACKER_BRIDGE_KEYS']=json.dumps({'CERRO_EL_PLOMO':'qa-only-key','other':'qa-only-key'})
    with factory() as db:
        db.get(Tenant,'t1').issuer='CERRO_EL_PLOMO'
        db.get(Tenant,'t2').issuer='CERRO_EL_PLOMO';db.get(Tenant,'t2').company_id=2
        db.add(Tenant(id='t3',issuer='other',company_id=1,name='Other issuer'))
        db.add(DeviceRegistration(id='r1',tenant_id='t1',device_id='d1'))
        db.commit()
    return client,factory


def configure(client,mode,version,**extra):
    return client.post('/v1/configuration/devices/r1/commissioning',headers=auth(),json={'mode':mode,'version':version,'reason':'Prueba física de instalación',**extra})


def observe(client,**extra):
    stamp=now().isoformat()
    return client.post('/v1/receiver/poll',headers=auth('ingestor'),json={'release':'qa','observations':[{'imei':'123456789012345','last_seen_at':stamp,'fix_at':stamp,'fix_received_at':stamp,'lat':-33,'lon':-70,**extra}]})


def test_capture_to_live_ingestion_and_revocation(setup):
    client,factory=setup
    assert configure(client,'forward',1,verified=True).status_code==422
    assert configure(client,'capture',1).json()['version']==2
    result=observe(client)
    assert result.status_code==200 and result.json()['devices'][0]['mode']=='capture'
    inventory=client.get('/v1/configuration',headers=auth()).json()
    assert inventory['receiver']['online'] is True
    assert inventory['items'][0]['version']==2  # heartbeat never conflicts with an open form
    assert inventory['items'][0]['commissioning']['lat']==-33
    assert configure(client,'forward',1,verified=True).status_code==409
    assert configure(client,'forward',2).status_code==422
    assert configure(client,'forward',2,verified=True).json()['version']==3
    payload={'device_id':'d1','source_id':'gps103:qa-event','recorded_at':now().isoformat(),'lat':-33,'lon':-70,'quality':'gps'}
    assert client.post('/v1/ingest/positions',headers=auth('ingestor'),json=payload).status_code==200
    assert client.get('/v1/assets/a1',headers=auth('viewer')).json()['last_position']['lat']==-33
    assert configure(client,'disabled',3).status_code==200
    payload['source_id']='gps103:revoked'
    assert client.post('/v1/ingest/positions',headers=auth('ingestor'),json=payload).status_code==403
    assert observe(client).json()['devices']==[]
    with factory() as db:assert db.query(Position).count()==1


def test_roles_and_companies_never_disclose_inventory(setup):
    client,_=setup
    for role in ('viewer','operator','manager'):
        assert client.post('/v1/receiver/poll',headers=auth(role),json={'release':'qa'}).status_code==403
    for role in ('viewer','operator','ingestor'):
        assert client.post('/v1/configuration/devices/r1/commissioning',headers=auth(role),json={'mode':'capture','version':1,'reason':'Test scope'}).status_code==403
    assert client.post('/v1/configuration/devices/r1/commissioning',headers=auth(company=2),json={'mode':'capture','version':1,'reason':'Test scope'}).status_code==404
    assert client.post('/v1/receiver/poll',headers=auth('ingestor',issuer='other'),json={'release':'qa'}).status_code==403
    configure(client,'capture',1);observe(client)
    other=client.get('/v1/configuration',headers=auth(company=2)).json()
    assert other['items']==[] and other['receiver']['online'] is False


def test_stale_or_future_diagnostics_cannot_activate(setup):
    client,_=setup
    configure(client,'capture',1)
    assert observe(client,fix_at=(now()+timedelta(hours=1)).isoformat()).status_code==422
    observe(client,fix_at=(now()-timedelta(minutes=10)).isoformat())
    assert configure(client,'forward',2,verified=True).status_code==422
    assert observe(client,lat=None,lon=None).status_code==200
    assert configure(client,'forward',2,verified=True).status_code==422


def test_reassociation_requires_new_fix_and_physical_check(setup):
    client,_=setup
    configure(client,'capture',1);observe(client);configure(client,'forward',2,verified=True)
    result=client.post('/v1/configuration/devices/r1/assignment',headers=auth(),json={'asset_id':None,'version':3,'reason':'Retirar equipo de prueba'})
    assert result.status_code==200
    assert client.get('/v1/configuration',headers=auth()).json()['items'][0]['commissioning']['mode']=='capture'
    assert configure(client,'forward',4,verified=True).status_code==422
    assert client.post('/v1/configuration/devices/r1/assignment',headers=auth(),json={'asset_id':'a1','version':4,'reason':'Nueva instalación física'}).status_code==200
    assert configure(client,'forward',5,verified=True).status_code==422
    observe(client)
    assert configure(client,'forward',5,verified=True).status_code==200


def test_extra_receiver_tenant_is_explicit_and_scoped(setup,tmp_path,monkeypatch):
    client,factory=setup
    policy=tmp_path/'allowed.json';policy.write_text(json.dumps([{'issuer':'LAB_TAREAS','company_id':1}]))
    monkeypatch.setenv('TRACKER_COBAN_TENANTS_FILE',str(policy))
    os.environ['TRACKER_BRIDGE_KEYS']=json.dumps({'CERRO_EL_PLOMO':'qa-only-key','LAB_TAREAS':'qa-only-key'})
    with factory() as db:
        db.add_all([Tenant(id='dev1',issuer='LAB_TAREAS',company_id=1,name='Development'),Tenant(id='dev2',issuer='LAB_TAREAS',company_id=2,name='Excluded')]);db.commit()
    assert client.post('/v1/receiver/poll',headers=auth('ingestor',1,'LAB_TAREAS'),json={'release':'qa'}).status_code==200
    assert client.post('/v1/receiver/poll',headers=auth('ingestor',2,'LAB_TAREAS'),json={'release':'qa'}).status_code==403
    assert client.post('/v1/receiver/poll',headers=auth('manager',1,'LAB_TAREAS'),json={'release':'qa'}).status_code==403
    policy.write_text('invalid')
    assert client.post('/v1/receiver/poll',headers=auth('ingestor',1,'LAB_TAREAS'),json={'release':'qa'}).status_code==403
