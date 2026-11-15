"""I11 against a disposable copy of the Development Tracker database."""
from datetime import datetime, timedelta, timezone
import uuid

from fastapi import HTTPException, Response
from sqlalchemy.orm import Session

from app.db.session import engine
from app.models.cost_centers import CostCenter
from app.models.machines import Machine
from app.models.mobile import MobileRoute
from app.models.users import User, UserCostCenter
from app.routers.passenger_services import (
    EventIn, ProgressIn, ServiceIn, create_service, get_manifest,
    list_service_progress, record_event, record_progress,
)
from rehearse_passenger_services import snapshot


def check(db):
    now = datetime.now(timezone.utc)
    center = CostCenter(name='Private I11 center', created_at=now)
    db.add(center)
    db.flush()
    admin, driver = [User(username='private-i11-' + uuid.uuid4().hex, full_name='Private I11 user',
                          password_hash='unusable', is_admin=is_admin, is_active=True, created_at=now)
                     for is_admin in (True, False)]
    db.add_all([admin, driver])
    db.flush()
    db.add(UserCostCenter(user_id=driver.id, cost_center_id=center.id))
    van = Machine(name='Private I11 vehicle', cost_center_id=center.id, is_active=True,
                  passenger_capacity=3, created_at=now)
    db.add(van)
    db.flush()
    route = MobileRoute(name='Private I11 route', machine_id=van.id, waypoints=[],
                        created_by=admin.id, status='assigned')
    db.add(route)
    db.flush()
    first, second, passenger = [uuid.uuid4() for _ in range(3)]
    service = ServiceIn(id=uuid.uuid4(), name='Private I11 service', route_id=route.id,
                        driver_user_id=driver.id,
                        stops=[{'id': first, 'name': 'Origen', 'scheduled_at': now - timedelta(minutes=10)},
                               {'id': second, 'name': 'Destino', 'scheduled_at': now + timedelta(minutes=15)}],
                        passengers=[{'id': passenger, 'name': 'Private passenger', 'document': 'QA1',
                                     'boarding_stop_id': first, 'alighting_stop_id': second}])
    create_service(service, Response(), db, admin)
    for version, (stop, kind) in enumerate(
        [(first, 'arrived'), (first, 'departed'), (second, 'arrived'), (second, 'departed')]
    ):
        payload = ProgressIn(id=uuid.uuid4(), kind=kind, stop_id=stop, expected_version=version,
                             notes='Desvío informado' if version == 0 else None)
        result = record_progress(service.id, payload, Response(), db, driver)
        assert record_progress(service.id, payload, Response(), db, driver)['version'] == version + 1
        if version == 0:
            assert result['stops'][0]['delay_minutes'] >= 10 and result['stops'][1]['eta']
            visible = next(item for item in list_service_progress(Response(), db, admin)
                           if item['id'] == str(service.id))
            assert visible['stops'][0]['arrival_notes'] == 'Desvío informado'
            assert 'passengers' not in visible
    record_event(service.id, EventIn(id=uuid.uuid4(), passenger_id=passenger, kind='no_show',
                                     expected_version=0, occurred_at=now), Response(), db, driver)
    manifest = get_manifest(service.id, Response(), db, driver)
    signed = ProgressIn(id=uuid.uuid4(), kind='closed', expected_version=4,
                        manifest_version=manifest['manifest_version'], signature='Private I11 driver',
                        notes='Cierre de prueba')
    closed = record_progress(service.id, signed, Response(), db, driver)['closure']
    assert closed['manifest_hash'] == manifest['sync']['content_hash'] and closed['actor_id'] == driver.id
    try:
        record_event(service.id, EventIn(id=uuid.uuid4(), passenger_id=passenger, kind='boarded',
                                         expected_version=1, occurred_at=now), Response(), db, driver)
    except HTTPException as exc:
        assert exc.status_code == 409
    else:
        raise AssertionError('A closed manifest accepted additional boarding')


if __name__ == '__main__':
    assert engine.url.database.startswith('TRACKER_I11_QA_')
    with engine.connect() as connection:
        columns, before = snapshot(connection)
    with engine.connect() as connection:
        outer = connection.begin()
        try:
            with Session(bind=connection, join_transaction_mode='create_savepoint') as session:
                check(session)
        finally:
            outer.rollback()
    with engine.connect() as connection:
        assert snapshot(connection, columns)[1] == before
    print('TRACKER_I11_POSTGRES_OK arrivals departures delay coordinator closure rollback')
