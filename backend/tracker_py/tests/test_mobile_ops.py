import base64
from datetime import date
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
import app.models as _models  # noqa: F401  registra todas las tablas
from app.db.base import Base
from app.db.session import get_db
from app.core.security import get_current_user
from app.routers import mobile as mobile_router
from app.models.activities import Activity, Labor
from app.models.cost_centers import CostCenter
from app.models.machines import Machine
from app.models.users import User, UserCostCenter
from app.models.work_orders import WorkOrder


@compiles(JSONB, 'sqlite')
def _jsonb_sqlite(type_, compiler, **kw):
    return 'JSON'


JPEG = base64.b64encode(b'\xff\xd8\xff\xe0' + b'0' * 64).decode()


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(mobile_router, 'MEDIA_DIR', str(tmp_path))
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        db.add_all([CostCenter(id=1, name='Campo A'), CostCenter(id=2, name='Campo B')])
        db.add(Activity(id=1, name='Cosecha', is_active=True))
        db.flush()
        db.add(Labor(id=1, activity_id=1, name='Cosechar', is_active=True))
        db.add_all([Machine(id=1, name='Tractor A', is_active=True, cost_center_id=1), Machine(id=2, name='Tractor B', is_active=True, cost_center_id=2)])
        db.add_all([User(id=1, username='admin', full_name='Ana Admin', password_hash='x', is_admin=True),
                    User(id=2, username='op', full_name='Omar Operador', password_hash='x', is_admin=False),
                    User(id=3, username='sin', full_name='Sin Centros', password_hash='x', is_admin=False)])
        db.flush()
        db.add(UserCostCenter(user_id=2, cost_center_id=1))
        db.add(WorkOrder(id=10, code='T1', work_date=date(2026, 10, 2), season='2026', activity_id=1, labor_id=1, cost_center_id=1, machine_id=1, assigned_user_id=2, scheduled_time='08:00'))
        db.commit()
    who = {'id': 2}

    def override_db():
        with factory() as db:
            yield db

    def current():
        with factory() as db:
            return db.get(User, who['id'])

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = current
    yield TestClient(app), who, factory
    app.dependency_overrides.clear()
    engine.dispose()


def test_admin_sees_all_cost_centers_and_operator_only_assigned(api):
    client, who, _ = api
    who['id'] = 1
    assert {c['id'] for c in client.get('/auth/me/cost_centers').json()} == {1, 2}
    who['id'] = 2
    assert {c['id'] for c in client.get('/auth/me/cost_centers').json()} == {1}
    who['id'] = 3
    assert client.get('/auth/me/cost_centers').json() == []


def test_refresh_returns_new_token(api):
    client, who, _ = api
    r = client.post('/auth/refresh')
    assert r.status_code == 200 and r.json()['access_token'] and r.json()['user']['id'] == 2


def test_incident_is_idempotent_isolated_and_attendable(api):
    client, who, _ = api
    iid = str(uuid.uuid4())
    body = {'id': iid, 'category': 'breakdown', 'machine_id': 1, 'note': 'No parte', 'lat': -35.4, 'lon': -71.6, 'photo_b64': JPEG}
    first = client.post('/mobile/incidents', json=body)
    again = client.post('/mobile/incidents', json=body)
    assert first.status_code == 200 and again.status_code == 200 and first.json()['has_photo'] is True
    assert len(client.get('/mobile/incidents').json()) == 1
    assert client.get(f'/mobile/photos/incidents/{iid}').status_code == 200
    # maquina de un centro ajeno
    assert client.post('/mobile/incidents', json={'id': str(uuid.uuid4()), 'category': 'damage', 'machine_id': 2}).status_code == 403
    assert client.post('/mobile/incidents', json={'id': str(uuid.uuid4()), 'category': 'raro'}).status_code == 400
    assert client.post('/mobile/incidents', json={'id': str(uuid.uuid4()), 'category': 'damage', 'machine_id': 1, 'photo_b64': base64.b64encode(b'no es imagen').decode()}).status_code == 400
    assert client.patch(f'/mobile/incidents/{iid}', json={'status': 'attended'}).status_code == 403
    who['id'] = 1
    assert client.patch(f'/mobile/incidents/{iid}', json={'status': 'attended'}).json()['status'] == 'attended'
    assert [i['status'] for i in client.get('/mobile/incidents?status=attended').json()] == ['attended']


def test_checklist_and_expenses(api):
    client, who, _ = api
    assert len(client.get('/mobile/checklist_template').json()['items']) >= 6
    cid = str(uuid.uuid4())
    body = {'id': cid, 'machine_id': 1, 'items': [{'key': 'lights', 'label': 'Luces', 'ok': True}, {'key': 'brakes', 'label': 'Frenos', 'ok': False, 'note': 'Ruido'}]}
    assert client.post('/mobile/checklists', json=body).json()['all_ok'] is False
    assert client.post('/mobile/checklists', json=body).status_code == 200
    eid = str(uuid.uuid4())
    fuel = {'id': eid, 'kind': 'fuel', 'machine_id': 1, 'liters': 40, 'amount': 52000, 'station': 'Copec', 'odometer': 1234.5, 'photo_b64': JPEG}
    assert client.post('/mobile/expenses', json=fuel).json()['liters'] == 40
    assert client.post('/mobile/expenses', json=fuel).status_code == 200
    assert client.post('/mobile/expenses', json={'id': str(uuid.uuid4()), 'kind': 'fuel', 'machine_id': 1}).status_code == 400
    assert len(client.get('/mobile/expenses').json()) == 1
    who['id'] = 3
    assert client.get('/mobile/expenses').json() == []
    assert client.get(f'/mobile/photos/expenses/{eid}').status_code == 403


def test_my_tasks_and_progress(api):
    client, who, _ = api
    mine = client.get('/work_orders?mine=true').json()
    assert [w['id'] for w in mine] == [10] and mine[0]['scheduled_time'] == '08:00'
    upd = client.put('/work_orders/10', json={'mobile_status': 'in_progress', 'progress_pct': 40})
    assert upd.status_code == 200 and upd.json()['progress_pct'] == 40
    assert client.put('/work_orders/10', json={'assigned_user_id': 3}).status_code == 403
    who['id'] = 3
    assert client.get('/work_orders?mine=true').json() == []
    who['id'] = 1
    assert client.put('/work_orders/10', json={'assigned_user_id': 3}).json()['assigned_user_id'] == 3


def test_heartbeat_and_devices(api):
    client, who, _ = api
    assert client.post('/mobile/heartbeat', json={'version': '0.4.0', 'platform': 'web', 'pending': 3}).status_code == 200
    assert client.get('/mobile/devices').status_code == 403
    assert client.post('/mobile/diagnostics', json={'version': '0.4.0', 'message': 'falla', 'log': 'x'}).status_code == 200
    who['id'] = 1
    devices = client.get('/mobile/devices').json()
    assert devices[0]['version'] == '0.4.0' and devices[0]['pending'] == 3 and devices[0]['user_name'] == 'Omar Operador'
