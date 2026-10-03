import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

from app.main import app
import app.models as _models  # noqa: F401  registra todas las tablas
from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.core.security import get_current_user
from app.models.activities import Activity, Labor
from app.models.cost_centers import CostCenter
from app.models.machines import Machine
from app.models.sessions import TrackingSession, TrackingStatus
from app.models.users import User, UserCostCenter
from app.models.work_orders import WorkOrder
from app.models.drivers import Driver
from app.models.implements import Implement
from app.models.fields import Field

@compiles(JSONB, 'sqlite')
def _jsonb_sqlite(type_, compiler, **kw):
    return 'JSON'


TABLES = [CostCenter, Machine, Activity, Labor, WorkOrder, TrackingSession, User, UserCostCenter, Driver, Implement, Field]


@pytest.fixture
def api():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        db.add(User(id=1, username='ana', full_name='Ana QA', password_hash='test-only', is_admin=True, is_active=True))
        db.add(CostCenter(id=1, name='Campo'))
        db.add(Activity(id=1, name='Cosecha', is_active=True))
        db.flush()
        db.add(Labor(id=1, activity_id=1, name='Cosechar', is_active=True))
        db.add(Machine(id=1, name='Tractor', is_active=True, cost_center_id=1))
        db.commit()

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: User(id=1, username='ana', is_admin=True)
    yield TestClient(app), factory
    app.dependency_overrides.clear()
    engine.dispose()


WO = {'code': 'WO-offline-1', 'work_date': '2026-10-02', 'season': '2026', 'machine_id': 1, 'activity_id': 1, 'labor_id': 1, 'cost_center_id': 1}


def test_work_order_retry_does_not_duplicate(api):
    client, factory = api
    first = client.post('/work_orders', json=WO)
    again = client.post('/work_orders', json=WO)
    assert first.status_code == 200 and again.status_code == 200
    assert first.json()['id'] == again.json()['id']
    with factory() as db:
        assert db.query(WorkOrder).count() == 1


def test_session_start_with_client_id_is_idempotent(api):
    client, factory = api
    wo = client.post('/work_orders', json=WO).json()['id']
    sid = str(uuid.uuid4())
    body = {'id': sid, 'machine_id': 1, 'cost_center_id': 1, 'work_order_id': wo, 'started_at': '2026-10-02T08:00:00Z'}
    first = client.post('/sessions/start', json=body)
    again = client.post('/sessions/start', json=body)
    assert first.status_code == 200 and again.status_code == 200
    assert first.json()['id'] == again.json()['id'] == sid
    with factory() as db:
        assert db.query(TrackingSession).count() == 1


def test_session_start_without_id_keeps_working(api):
    client, _ = api
    r = client.post('/sessions/start', json={'machine_id': 1, 'cost_center_id': 1})
    assert r.status_code == 200 and r.json()['id']


def test_recovery_list_returns_work_order_and_preserves_offline_retry(api):
    client, factory = api
    wo = client.post('/work_orders', json=WO).json()['id']
    sid = str(uuid.uuid4())
    body = {'id': sid, 'machine_id': 1, 'cost_center_id': 1, 'work_order_id': wo}
    assert client.post('/sessions/start', json=body).status_code == 200
    with factory() as db:
        session = db.get(TrackingSession, uuid.UUID(sid))
        session.total_distance_m = 1200
        db.commit()
    listed = client.get('/sessions/my?status=open').json()
    assert len(listed) == 1
    assert listed[0]['work_order_id'] == wo
    assert listed[0]['total_distance_m'] == 1200
    assert client.post(f'/sessions/{sid}/close').status_code == 200
    assert client.get('/sessions/my?status=open').json() == []
    again = client.post('/sessions/start', json=body)
    assert again.json()['status'] == TrackingStatus.closed.value
    with factory() as db:
        assert db.query(TrackingSession).count() == 1
