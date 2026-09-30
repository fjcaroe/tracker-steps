import json
import os
from datetime import timedelta
import pytest
import subprocess
import sys
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.models.fleet import Tenant, Asset, Device, Assignment, Position, Policy, Incident, Audit, Preference, Command, now
from app.routers.fleet import check_communications

MODELS = [Tenant, Asset, Device, Assignment, Position, Policy, Incident, Audit, Preference, Command]


@pytest.fixture
def fleet():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[m.__table__ for m in MODELS])
    factory = sessionmaker(bind=engine)
    with factory() as db:
        db.add_all([Tenant(id='t1', issuer='test-one', company_id=1, name='One'), Tenant(id='t2', issuer='test-two', company_id=1, name='Two')])
        db.add_all([Asset(id='a1', tenant_id='t1', source_id='fleet:1', name='Tractor Norte', type='tractor'), Asset(id='a2', tenant_id='t2', source_id='fleet:1', name='Camión Sur', type='truck')])
        db.add(Device(id='d1', imei='123456789012345', brand='Coban', model='401C', freshness_seconds=300))
        db.add(Assignment(id='as1', tenant_id='t1', device_id='d1', asset_id='a1', valid_from=now()-timedelta(days=10)))
        db.commit()
    def override():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = override
    os.environ['TRACKER_BRIDGE_KEYS'] = json.dumps({'test-one': 'test-key-one', 'test-two': 'test-key-two'})
    yield TestClient(app), factory
    app.dependency_overrides.clear()
    engine.dispose()


def headers(issuer='test-one', role='manager', user='u1', company=1):
    stamp = int(now().timestamp())
    token = jwt.encode({'iss': issuer, 'aud': 'steps-tracker-v1', 'sub': user, 'iat': stamp, 'exp': stamp+60, 'role': role, 'company_id': company}, 'test-key-one' if issuer == 'test-one' else 'test-key-two', algorithm='HS256')
    return {'Authorization': 'Bearer '+token}


def point(source='event-1', minutes=0, **kw):
    return {'device_id': 'd1', 'source_id': source, 'recorded_at': (now()-timedelta(minutes=minutes)).isoformat(), 'lat': -35.4, 'lon': -71.6, 'speed_kmh': 4, 'quality': 'gps', **kw}


def test_auth_and_tenant_isolation(fleet):
    client, _ = fleet
    assert client.get('/v1/fleet/snapshot').status_code == 401
    assert client.get('/v1/fleet/snapshot', headers=headers(company=99)).status_code == 401
    for issuer, expected in [('test-one', 'a1'), ('test-two', 'a2')]:
        response = client.get('/v1/fleet/snapshot', headers=headers(issuer)).json()
        assert [a['asset_id'] for a in response['items']] == [expected]
    for path in ['/v1/assets/a2', '/v1/assets/a2/positions']:
        assert client.get(path, headers=headers()).status_code == 404
    assert client.put('/v1/security/policies', headers=headers(), json={'asset_id': 'a2', 'armed': True, 'version': 0, 'reason': 'Prueba cruce'}).status_code == 404
    assert client.post('/v1/ingest/positions', headers=headers('test-two', 'ingestor'), json=point()).status_code == 403


def test_ingestion_without_session_dedup_and_delayed_point(fleet):
    client, factory = fleet
    first = client.post('/v1/ingest/positions', headers=headers(role='ingestor'), json=point()).json()
    assert first['duplicate'] is False
    assert client.post('/v1/ingest/positions', headers=headers(role='ingestor'), json=point()).json()['duplicate'] is True
    assert client.post('/v1/ingest/positions', headers=headers(role='ingestor'), json=point('old', 60, lat=-36)).status_code == 200
    snap = client.get('/v1/fleet/snapshot', headers=headers()).json()['items'][0]
    assert snap['last_position']['id'] == first['id']
    assert snap['motion_state'] == 'moving'
    assert snap['capabilities']['remote_start_inhibit'] == 'not_approved'
    assert client.get('/v1/assets/a1/positions?limit=1', headers=headers()).json()['next_cursor'] == first['id']
    with factory() as db:
        assert db.query(Position).count() == 2


def test_old_fix_received_now_never_means_stopped(fleet):
    client, _ = fleet
    client.post('/v1/ingest/positions', headers=headers(role='ingestor'), json=point(minutes=60, speed_kmh=0))
    snap = client.get('/v1/assets/a1', headers=headers()).json()
    assert snap['signal_state'] == 'received'
    assert snap['position_stale'] is True
    assert snap['motion_state'] == 'unknown'


def test_reassignment_preserves_history(fleet):
    client, factory = fleet
    client.post('/v1/ingest/positions', headers=headers(role='ingestor'), json=point(minutes=60))
    with factory() as db:
        boundary = now()-timedelta(minutes=30)
        db.get(Assignment, 'as1').valid_to = boundary
        db.add(Assignment(id='as2', tenant_id='t2', device_id='d1', asset_id='a2', valid_from=boundary))
        db.commit()
    assert client.post('/v1/ingest/positions', headers=headers(role='ingestor'), json=point('new-wrong')).status_code == 403
    assert client.post('/v1/ingest/positions', headers=headers('test-two', 'ingestor'), json=point('new-right')).status_code == 200
    assert len(client.get('/v1/assets/a1/positions', headers=headers()).json()['items']) == 1
    assert len(client.get('/v1/assets/a2/positions', headers=headers('test-two')).json()['items']) == 1
    assert client.get('/v1/assets/a1', headers=headers()).json()['last_position'] is None


def test_filters_preferences_and_roles(fleet):
    client, _ = fleet
    assert client.get('/v1/fleet/snapshot?type=tractor&signal=no_signal&q=Norte', headers=headers()).json()['total'] == 1
    assert client.get('/v1/fleet/snapshot?type=tractor&signal=received', headers=headers()).json()['total'] == 0
    pref = {'columns': ['name', 'signal_state'], 'filters': {'q': 'Norte'}}
    assert client.put('/v1/view-preferences/fleet', headers=headers(), json=pref).status_code == 200
    assert client.get('/v1/view-preferences/fleet', headers=headers(user='u2')).json() is None
    assert client.get('/v1/view-preferences/fleet', headers=headers('test-two')).json() is None
    assert client.put('/v1/view-preferences/fleet', headers=headers(), json={**pref, 'columns': ['password']}).status_code == 422
    assert client.put('/v1/assets', headers=headers(role='viewer'), json={'name': 'A', 'source_id': 'X'}).status_code == 403
    assert client.post('/v1/ingest/positions', headers=headers(), json=point()).status_code == 403


def test_incident_grouping_ack_close_audit_and_negative_commands(fleet):
    client, factory = fleet
    body = {'asset_id': 'a1', 'armed': True, 'version': 0, 'reason': 'Proteger de noche'}
    assert client.put('/v1/security/policies', headers=headers(), json=body).status_code == 200
    assert client.put('/v1/security/policies', headers=headers(), json=body).status_code == 409
    for event in ('event1', 'event2'):
        assert client.post('/v1/ingest/positions', headers=headers(role='ingestor'), json=point(event, external_power=False)).status_code == 200
    rows = client.get('/v1/security/incidents', headers=headers()).json()['items']
    assert {r['type'] for r in rows} == {'external_power_lost', 'suspected_movement'}
    incident = rows[0]['id']
    assert client.get('/v1/security/incidents/'+incident, headers=headers('test-two')).status_code == 404
    assert client.patch('/v1/security/incidents/'+incident, headers=headers(), json={'state': 'closed', 'reason': 'Uso autorizado'}).status_code == 409
    command = {'incident_id': incident, 'intention_id': 'unique-intent', 'type': 'inhibit_next_start', 'reason': 'Revisar incidente'}
    assert client.post('/v1/security/commands', headers=headers(role='viewer'), json=command).status_code == 403
    result = client.post('/v1/security/commands', headers=headers(), json=command).json()
    assert result['state'] == 'failed'
    assert client.post('/v1/security/commands', headers=headers(), json=command).json()['id'] == result['id']
    assert client.post('/v1/security/commands/'+result['id']+'/approve', headers=headers(user='second')).status_code == 409
    for state in ('acknowledged', 'closed'):
        response = client.patch('/v1/security/incidents/'+incident, headers=headers(), json={'state': state, 'reason': 'Falsa alarma comprobada'})
        assert response.status_code == 200
        assert response.json()['timeline'][-1]['action'] == state
    with factory() as db:
        assert db.query(Command).count() == 1
        assert db.query(Audit).filter_by(action='command_denied').count() == 2


def test_signal_monitor_distinguishes_communication_failure(fleet):
    client, factory = fleet
    client.put('/v1/security/policies', headers=headers(), json={'asset_id': 'a1', 'armed': True, 'version': 0, 'reason': 'Prueba cobertura'})
    with factory() as db:
        db.get(Policy, 'a1').updated_at = now()-timedelta(minutes=10)
        db.commit()
        check_communications(db)
        check_communications(db)
    rows = client.get('/v1/security/incidents', headers=headers()).json()['items']
    assert [r['type'] for r in rows] == ['communication_failure']


def test_incremental_change_feed_delivers_later_updates(fleet):
    client, _ = fleet
    row = client.post('/v1/security/incidents', headers=headers(), json={'asset_id': 'a1', 'type': 'manual', 'reason': 'Prueba inicial'}).json()
    first = client.get('/v1/sync/changes?limit=1', headers=headers()).json()
    assert first['has_more'] is True
    second = client.get('/v1/sync/changes', params={'cursor': first['cursor']}, headers=headers()).json()
    assert second['has_more'] is False
    client.patch('/v1/security/incidents/'+row['id'], headers=headers(), json={'state': 'acknowledged', 'reason': 'Operador verificó'})
    third = client.get('/v1/sync/changes', params={'cursor': second['cursor']}, headers=headers()).json()
    assert third['items'][0]['incident']['state'] == 'acknowledged'
    assert client.get('/v1/sync/changes', headers=headers('test-two')).json()['items'] == []
    assert client.get('/v1/sync/changes', headers=headers(role='viewer')).status_code == 403


def test_standalone_signal_worker_registers_all_models(tmp_path):
    url = 'sqlite:///'+str(tmp_path/'worker.db')
    engine = create_engine(url)
    Base.metadata.create_all(engine, tables=[m.__table__ for m in MODELS])
    engine.dispose()
    result = subprocess.run([sys.executable, 'scripts/check_gps_signal.py'], env={**os.environ, 'DATABASE_URL': url, 'PYTHONPATH': '.'}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_buffered_point_before_arming_does_not_raise_new_incident(fleet):
    client, _ = fleet
    buffered = point('before-arm', minutes=1, external_power=False)
    client.put('/v1/security/policies', headers=headers(), json={'asset_id': 'a1', 'armed': True, 'version': 0, 'reason': 'Armado posterior'})
    assert client.post('/v1/ingest/positions', headers=headers(role='ingestor'), json=buffered).status_code == 200
    assert client.get('/v1/security/incidents', headers=headers()).json()['items'] == []
