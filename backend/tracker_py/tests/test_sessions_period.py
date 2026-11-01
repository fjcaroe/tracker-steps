"""Contrato serializado de sesiones: IDs de origen y paginación por período."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.activities import Labor
from app.models.cost_centers import CostCenter
from app.models.drivers import Driver
from app.models.enums import TrackingStatus
from app.models.machines import Machine
from app.models.sessions import TrackingPoint, TrackingSession
from app.models.users import User
from app.models.work_orders import WorkOrder

TABLES = [m.__table__ for m in (User, CostCenter, Machine, Driver, Labor, WorkOrder, TrackingSession, TrackingPoint)]
T0 = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)


def _session(machine_id=1, start=T0, hours=1.0, distance_m=12345.0, status=TrackingStatus.closed, **kw):
    end = start + timedelta(hours=hours) if status == TrackingStatus.closed else None
    return TrackingSession(
        id=uuid.uuid4(), machine_id=machine_id, started_at=start, ended_at=end, status=status,
        total_distance_m=distance_m, points_count=5, **kw,
    )


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=TABLES)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        db.add(CostCenter(id=7, name="Cuartel Norte"))
        db.add_all([Machine(id=1, name="Tractor 1"), Machine(id=2, name="Tractor 2")])
        db.add(Driver(id=3, name="Conductora Uno"))
        db.commit()

    def override_db():
        with factory() as db:
            yield db

    admin = User(id=1, username="admin", full_name="Admin", password_hash="x", is_admin=True, is_active=True)
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: admin
    yield TestClient(app), factory
    app.dependency_overrides.clear()
    engine.dispose()


def _seed(factory, *sessions):
    with factory() as db:
        db.add_all(sessions)
        db.commit()


def test_serialized_sessions_carry_driver_and_cost_center_ids(client):
    """El response_model no debe descartar los IDs que consume el espejo Odoo."""
    http, factory = client
    row = _session(driver_id=3, cost_center_id=7)
    _seed(factory, row)
    params = {"from": "2026-09-01T00:00:00Z", "to": "2026-10-01T00:00:00Z"}
    for path, extra in (("/sessions_recent", {"limit": 10}), ("/sessions/search", params), ("/sessions/period", params)):
        body = http.get(path, params=extra).json()
        items = body["items"] if isinstance(body, dict) else body
        assert len(items) == 1, path
        assert items[0]["driver_id"] == 3, path
        assert items[0]["cost_center_id"] == 7, path
        assert items[0]["driver_name"] == "Conductora Uno", path
        assert items[0]["total_distance_m"] == 12345.0, path


def test_missing_driver_and_cost_center_stay_null(client):
    http, factory = client
    _seed(factory, _session())
    item = http.get("/sessions_recent", params={"limit": 10}).json()[0]
    assert item["driver_id"] is None
    assert item["cost_center_id"] is None


def test_period_pagination_is_complete_and_stable(client):
    http, factory = client
    # 12 sesiones con el MISMO inicio para forzar el desempate por id del cursor
    _seed(factory, *[_session(start=T0) for _ in range(12)], *[_session(start=T0 + timedelta(hours=i + 2)) for i in range(5)])
    params = {"from": "2026-09-10T00:00:00Z", "to": "2026-09-11T00:00:00Z", "limit": 5}
    seen, cursor, pages = [], None, 0
    while True:
        query = dict(params, **({"cursor": cursor} if cursor else {}))
        body = http.get("/sessions/period", params=query).json()
        pages += 1
        assert body["total"] == 17
        seen += [item["id"] for item in body["items"]]
        if body["next_cursor"]:
            assert body["complete"] is False
            cursor = body["next_cursor"]
        else:
            assert body["complete"] is True
            break
    assert pages == 4
    assert len(seen) == len(set(seen)) == 17


def test_period_includes_sessions_crossing_the_lower_bound_and_open_ones(client):
    http, factory = client
    before = _session(start=T0 - timedelta(hours=14), hours=3)           # cruza el límite inferior
    outside = _session(start=T0 - timedelta(days=3), hours=1)                    # termina antes del período
    after = _session(start=T0 + timedelta(days=5))                               # empieza después
    still_open = _session(start=T0 - timedelta(hours=2), status=TrackingStatus.open, distance_m=None)
    _seed(factory, before, outside, after, still_open)
    body = http.get("/sessions/period", params={"from": "2026-09-10T00:00:00Z", "to": "2026-09-11T00:00:00Z"}).json()
    ids = {item["id"] for item in body["items"]}
    assert ids == {str(before.id), str(still_open.id)}
    closed_only = http.get("/sessions/period", params={"from": "2026-09-10T00:00:00Z", "to": "2026-09-11T00:00:00Z", "status": "closed"}).json()
    assert {item["id"] for item in closed_only["items"]} == {str(before.id)}


def test_period_filters_machine_and_rejects_bad_input(client):
    http, factory = client
    _seed(factory, _session(machine_id=1), _session(machine_id=2))
    window = {"from": "2026-09-10T00:00:00Z", "to": "2026-09-11T00:00:00Z"}
    body = http.get("/sessions/period", params=dict(window, machine_id=2)).json()
    assert [item["machine_id"] for item in body["items"]] == [2]
    assert http.get("/sessions/period", params={"from": window["to"], "to": window["from"]}).status_code == 400
    assert http.get("/sessions/period", params=dict(window, cursor="no-es-un-cursor")).status_code == 400
    assert http.get("/sessions/period", params=dict(window, limit=5000)).status_code == 422


def test_unknown_distance_is_not_zero(client):
    http, factory = client
    _seed(factory, _session(distance_m=None))
    item = http.get("/sessions/period", params={"from": "2026-09-10T00:00:00Z", "to": "2026-09-11T00:00:00Z"}).json()["items"][0]
    assert item["total_distance_m"] is None


def test_capabilities_advertise_period_contract(client):
    http, _ = client
    caps = http.get("/health/capabilities").json()["capabilities"]
    assert "sessions_period_v1" in caps and "session_summary_ids_v1" in caps
    assert "odoo_sync_v1" in caps  # los clientes existentes siguen viendo sus capacidades
