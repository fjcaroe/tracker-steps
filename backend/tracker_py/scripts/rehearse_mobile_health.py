"""Verify the device report and helpdesk lookup against a private Development copy."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.session import engine
from app.models.users import User
from app.routers.mobile import HeartbeatIn, heartbeat, list_devices
from rehearse_passenger_services import snapshot


def check(db):
    now = datetime.now(timezone.utc)
    supervisor, driver = [
        User(username='private-i15-' + uuid4().hex, full_name='Private I15 ' + name,
             password_hash='unusable', is_admin=admin, is_active=True, created_at=now)
        for name, admin in (('supervisor', True), ('driver', False))
    ]
    db.add_all([supervisor, driver])
    db.flush()
    confirmed = now - timedelta(minutes=5)
    heartbeat(HeartbeatIn(version='1.9.0', platform='android', pending=0, last_sync_at=confirmed), db, driver)
    heartbeat(HeartbeatIn(version='1.9.0', platform='web', pending=2, last_sync_at=confirmed - timedelta(hours=1)),
              db, driver)
    heartbeat(HeartbeatIn(version='1.9.0', platform='web', pending=2), db, driver)
    report = next(record for record in list_devices(db, supervisor) if record.user_id == driver.id)
    assert report.user_name == 'Private I15 driver' and report.version == '1.9.0'
    assert report.pending == 2 and report.last_sync_at == confirmed
    assert report.platform == 'web' and report.last_seen_at >= now
    try:
        list_devices(db, driver)
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError('A driver could read the supervisor device list')


if __name__ == '__main__':
    assert engine.dialect.name == 'postgresql' and engine.url.database.startswith('TRACKER_I15_QA_')
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
    print('TRACKER_I15_POSTGRES_OK newest timestamp and supervisor access rollback')
