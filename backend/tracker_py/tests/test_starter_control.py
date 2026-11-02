import time
from datetime import timedelta
from jose import jwt
import pytest
from test_fleet import fleet, headers, point
from app.models.fleet import Device, DeviceRegistration, Command, now
from app.routers import starter_control as starter

def auth(scope=('a1',), preview=False, fresh=True):
    claims=jwt.get_unverified_claims(headers()['Authorization'].split()[1]);claims.update(role='operator',asset_ids=list(scope),starter_control=True,control_preview=preview,actuator_auth_at=time.time()-(0 if fresh else 120))
    return {'Authorization':'Bearer '+jwt.encode(claims,'test-key-one',algorithm='HS256')}

def setup(client,factory,**position):
    with factory() as db:
        db.get(Device,'d1').tracking_approved=True
        db.add(DeviceRegistration(id='r1',tenant_id='t1',device_id='d1',receiver_mode='forward',starter_relay_verified=True));db.commit()
    assert client.post('/v1/ingest/positions',headers=headers(role='ingestor'),json=point(speed_kmh=0,acc=False,**position)).status_code==200

def intention(action='inhibit_next_start',**values):
    return dict(intention_id='unique-action',type=action,reason='Supervised installation',plate_confirmation='TEST01',present=True,engine_off=True,**values)

def prepare(fleet):
    c,f=fleet
    from app.models.fleet import Asset
    with f() as db:db.get(Asset,'a1').plate='TEST01';db.commit()
    return c,f

def test_relay_scope_reauth_and_freshness(fleet,monkeypatch):
    c,f=prepare(fleet);setup(c,f)
    called=[];monkeypatch.setattr(starter,'relay',lambda data:called.append(data) or {'state':'sent_unconfirmed','detail':'Sent, not physically confirmed'})
    url='/v1/assets/a1/starter-control/commands';body=intention()
    assert c.post(url,headers=auth(scope=()),json=body).status_code==404
    assert c.post(url,headers=auth(preview=True),json=body).status_code==403
    assert c.post(url,headers=auth(fresh=False),json=body).status_code==403
    assert c.post(url,headers=auth(),json={**body,'plate_confirmation':'WRONG'}).status_code==422
    assert called==[]
    first=c.post(url,headers=auth(),json=body);assert first.status_code==200
    assert first.json()['state']=='sent_unconfirmed' and first.json()['confirmed_at'] is None
    assert len(called)==1
    repeated=c.post(url,headers=auth(),json=body);assert repeated.json()['id']==first.json()['id'] and len(called)==1
    assert c.post(url,headers=auth(),json={**body,'intention_id':'another-block'}).status_code==409
    wrong=c.post(url+'/'+first.json()['id']+'/confirm',headers=auth(),json=dict(observed='restored',present=True,reason='Physical test'))
    assert wrong.status_code==422
    assert c.post(url+'/'+first.json()['id']+'/confirm',headers=auth(),json=dict(observed='blocked',present=True,reason='Starter did not engage')).json()['state']=='confirmed'
    assert c.post(url,headers=auth(),json={**body,'intention_id':'restore-intention','type':'restore_start'}).json()['state']=='sent_unconfirmed'

@pytest.mark.parametrize('acc,speed,minutes',[(True,0,0),(None,0,0),(False,3,0),(False,0,2)])
def test_block_rejects_moving_unknown_ignition_or_old_fix(fleet,monkeypatch,acc,speed,minutes):
    c,f=prepare(fleet)
    with f() as db:
        db.get(Device,'d1').tracking_approved=True;db.add(DeviceRegistration(id='r1',tenant_id='t1',device_id='d1',receiver_mode='forward',starter_relay_verified=True));db.commit()
    c.post('/v1/ingest/positions',headers=headers(role='ingestor'),json=point(speed_kmh=speed,acc=acc,minutes=minutes))
    monkeypatch.setattr(starter,'relay',lambda data:pytest.fail('Rejected block reached actuator transport'))
    assert c.post('/v1/assets/a1/starter-control/commands',headers=auth(),json=intention()).status_code==409

def test_restore_does_not_require_gps_and_failures_are_not_success(fleet,monkeypatch):
    c,f=prepare(fleet)
    with f() as db:
        db.get(Device,'d1').tracking_approved=True;db.add(DeviceRegistration(id='r1',tenant_id='t1',device_id='d1',receiver_mode='forward',starter_relay_verified=True));db.commit()
    monkeypatch.setattr(starter,'relay',lambda data:{'state':'uncertain','detail':'Unknown delivery; no retry'})
    value=c.post('/v1/assets/a1/starter-control/commands',headers=auth(),json=intention('restore_start')).json()
    assert value['state']=='uncertain' and value['confirmed_at'] is None
    with f() as db:assert db.query(Command).count()==1
