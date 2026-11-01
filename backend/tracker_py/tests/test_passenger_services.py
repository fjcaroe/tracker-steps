"""Actual API/ORM contract: manifest creation, identity isolation and capacity."""
from copy import deepcopy
from datetime import datetime, timezone
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
import app.models as _models  # noqa: F401
from app.db.base import Base
from app.db.session import get_db
from app.core.security import get_current_user
from app.models.users import User, UserCostCenter
from app.models.cost_centers import CostCenter
from app.models.machines import Machine
from app.models.mobile import MobileRoute
from app.models.passenger_services import PassengerService, ServicePassenger, ServiceStop


@compiles(JSONB,'sqlite')
def jsonb_sqlite(type_,compiler,**kw):
    return 'JSON'


@pytest.fixture
def api():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    @event.listens_for(engine,'connect')
    def foreign_keys(connection,record):
        connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    factory=sessionmaker(bind=engine)
    route_id=uuid.uuid4()
    with factory() as db:
        db.add_all([CostCenter(id=1,name='Private CC'),CostCenter(id=2,name='Private other')]);db.flush()
        db.add_all([User(id=i,username='private-'+str(i),full_name='Private '+str(i),password_hash='test',is_active=True,is_admin=(i==1)) for i in range(1,5)])
        db.add(Machine(id=1,name='Private vehicle',plate='QA0046',cost_center_id=1,is_active=True,passenger_capacity=3))
        db.flush()
        db.add_all([UserCostCenter(user_id=i,cost_center_id=1) for i in (2,3)])
        db.add(MobileRoute(id=route_id,name='Private route',machine_id=1,waypoints=[],created_by=1,status='assigned'))
        db.commit()
    who={'id':1}
    def database():
        with factory() as db:
            yield db
    def current():
        with factory() as db:
            return db.get(User,who['id'])
    app.dependency_overrides[get_db]=database
    app.dependency_overrides[get_current_user]=current
    stops=[{'id':str(uuid.uuid4()),'name':name,'scheduled_at':at} for name,at in [('Origen','2026-11-02T08:00:00-03:00'),('Intermedia','2026-11-02T08:30:00-03:00'),('Destino','2026-11-02T09:00:00-03:00')]]
    body={'id':str(uuid.uuid4()),'name':'Private service','route_id':str(route_id),'driver_user_id':2,'stops':stops,
          'passengers':[{'id':str(uuid.uuid4()),'name':'Private passenger '+str(i),'document':'TEST-'+str(i),
                         'boarding_stop_id':stops[0]['id'],'alighting_stop_id':stops[2]['id'],'seat':i} for i in range(1,4)]}
    yield TestClient(app),who,factory,body
    app.dependency_overrides.clear();engine.dispose()


def test_acceptance_three_passengers_and_driver_only_visibility(api):
    client,who,_,body=api
    result=client.post('/mobile/services',json=body)
    assert result.status_code==200,result.text
    assert result.headers['cache-control']=='no-store'
    assert len(result.json()['passengers'])==3 and result.json()['capacity']==3
    who['id']=2
    own=client.get('/mobile/services')
    assert own.headers['cache-control']=='no-store' and [s['id'] for s in own.json()]==[body['id']]
    assert client.get('/mobile/services/'+body['id']).status_code==200
    who['id']=3  # Same cost center, different conductor.
    assert client.get('/mobile/services?mine=false').json()==[]
    assert client.get('/mobile/services/'+body['id']).status_code==404
    assert client.post('/mobile/services',json=body).status_code==403


def test_idempotency_and_conflicting_payload_are_atomic(api):
    client,_,factory,body=api
    assert client.post('/mobile/services',json=body).status_code==200
    assert client.post('/mobile/services',json=body).status_code==200
    changed=deepcopy(body);changed['name']='Other content'
    assert client.post('/mobile/services',json=changed).status_code==409
    with factory() as db:
        assert db.query(PassengerService).count()==1 and db.query(ServiceStop).count()==3 and db.query(ServicePassenger).count()==3


@pytest.mark.parametrize('kind',['over_capacity','seat_repeated','seat_outside','stop_foreign','backwards','duplicate_document','duplicate_stop','naive_time','bad_coordinates'])
def test_invalid_manifests_leave_no_records(api,kind):
    client,_,factory,body=api
    if kind=='over_capacity':
        person=deepcopy(body['passengers'][0]);person.update(id=str(uuid.uuid4()),name='Extra',document='EXTRA',seat=None);body['passengers'].append(person)
    elif kind=='seat_repeated':body['passengers'][1]['seat']=1
    elif kind=='seat_outside':body['passengers'][1]['seat']=4
    elif kind=='stop_foreign':body['passengers'][0]['boarding_stop_id']=str(uuid.uuid4())
    elif kind=='backwards':body['passengers'][0]['boarding_stop_id']=body['stops'][2]['id']
    elif kind=='duplicate_document':body['passengers'][1]['document']=body['passengers'][0]['document']
    elif kind=='duplicate_stop':body['stops'][1]['id']=body['stops'][0]['id']
    elif kind=='naive_time':body['stops'][0]['scheduled_at']='2026-11-02T08:00:00'
    elif kind=='bad_coordinates':body['stops'][0].update(lat=91,lon=0)
    result=client.post('/mobile/services',json=body)
    assert result.status_code==422,result.text
    with factory() as db:
        assert db.query(PassengerService).count()==db.query(ServiceStop).count()==db.query(ServicePassenger).count()==0


def test_seat_can_be_reused_on_non_overlapping_legs(api):
    client,_,_,body=api
    body['passengers'][0]['alighting_stop_id']=body['stops'][1]['id']
    body['passengers'][1]['boarding_stop_id']=body['stops'][1]['id'];body['passengers'][1]['seat']=1
    assert client.post('/mobile/services',json=body).status_code==200


def test_capacity_is_required_and_historical_capacity_is_preserved(api):
    client,_,factory,body=api
    with factory() as db:
        db.get(Machine,1).passenger_capacity=None;db.commit()
    assert client.post('/mobile/services',json=body).status_code==422
    with factory() as db:
        db.get(Machine,1).passenger_capacity=3;db.commit()
    assert client.post('/mobile/services',json=body).status_code==200
    assert client.put('/machines/1',json={'passenger_capacity':2}).status_code==200
    assert client.get('/mobile/services/'+body['id']).json()['capacity']==3
    assert client.put('/machines/1',json={'passenger_capacity':0}).status_code==422


def test_assignment_requires_active_driver_cost_center_and_live_access(api):
    client,who,factory,body=api
    body['driver_user_id']=4
    assert client.post('/mobile/services',json=body).status_code==403
    body['driver_user_id']=2
    assert client.post('/mobile/services',json=body).status_code==200
    with factory() as db:
        db.query(UserCostCenter).filter_by(user_id=2).delete();db.commit()
    who['id']=2
    assert client.get('/mobile/services').json()==[]
    assert client.get('/mobile/services/'+body['id']).status_code==403


def test_api_requires_authentication(api):
    client,_,_,_=api
    del app.dependency_overrides[get_current_user]
    assert client.get('/mobile/services').status_code==401


def test_route_cancellation_remains_visible_without_erasing_manifest(api):
    client,who,_,body=api
    assert client.post('/mobile/services',json=body).status_code==200
    assert client.patch('/mobile/routes/'+body['route_id'],json={'status':'cancelled'}).status_code==200
    who['id']=2
    service=client.get('/mobile/services/'+body['id']).json()
    assert service['route_status']=='cancelled' and len(service['passengers'])==3
