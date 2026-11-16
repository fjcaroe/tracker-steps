"""Verify the regular driver and supervisor incident workflow on a private copy."""
import time
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import engine
from app.models.cost_centers import CostCenter
from app.models.machines import Machine
from app.models.mobile import MobileIncident
from app.models.sessions import TrackingSession
from app.models.users import User, UserCostCenter
from app.routers.mobile import IncidentIn, create_incident, list_incidents
from rehearse_passenger_services import snapshot


def check(db):
    now = datetime.now(timezone.utc)
    center = CostCenter(name='Private I12 center', created_at=now)
    driver = User(username='private-i12-' + uuid4().hex, full_name='Private I12 driver',
                  password_hash='unusable', is_admin=False, is_active=True, created_at=now)
    supervisor = User(username='private-i12-' + uuid4().hex, full_name='Private I12 supervisor',
                      password_hash='unusable', is_admin=True, is_active=True, created_at=now)
    db.add_all([center, driver, supervisor])
    db.flush()
    db.add(UserCostCenter(user_id=driver.id, cost_center_id=center.id))
    machine = Machine(name='Private I12 vehicle', cost_center_id=center.id, is_active=True, created_at=now)
    db.add(machine)
    db.flush()
    session = TrackingSession(machine_id=machine.id, cost_center_id=center.id, started_at=now)
    db.add(session)
    db.flush()
    incident = IncidentIn(id=uuid4(), category='sos', machine_id=machine.id, session_id=session.id,
                          lat=-35.25, lon=-71.25, occurred_at=now)
    start = time.monotonic()
    posted = create_incident(incident, db, driver)
    visible = next(item for item in list_incidents(status=None, limit=100, db=db, current=supervisor)
                   if item.id == incident.id)
    assert time.monotonic() - start < 5, 'The SOS API exceeded the interval available before the next refresh'
    assert visible.id == posted.id and (visible.lat, visible.lon) == (-35.25, -71.25)
    assert visible.status == 'open' and visible.user_id == driver.id and visible.session_id == session.id
    assert visible.category == 'sos'
    assert create_incident(incident, db, driver).id == incident.id
    assert len(db.scalars(select(MobileIncident).where(MobileIncident.id == incident.id)).all()) == 1


if __name__ == '__main__':
    assert engine.dialect.name == 'postgresql' and engine.url.database.startswith('TRACKER_I12_QA_')
    with engine.connect() as connection:
        columns, before = snapshot(connection)
    with engine.connect() as connection:
        outer = connection.begin()
        try:
            with Session(bind=connection, join_transaction_mode='create_savepoint') as db:
                check(db)
        finally:
            outer.rollback()
    with engine.connect() as connection:
        assert snapshot(connection, columns)[1] == before
    print('TRACKER_I12_POSTGRES_OK sos idempotent supervisor location rollback')
