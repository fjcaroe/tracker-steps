"""I10 acceptance on a fresh private PostgreSQL copy; fixtures roll back."""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import Response, HTTPException
from sqlalchemy.orm import Session
from app.main import app  # noqa: F401
from app.db.session import engine
from app.models.users import User, UserCostCenter
from app.models.cost_centers import CostCenter
from app.models.machines import Machine
from app.models.mobile import MobileRoute
from app.models.passenger_services import PassengerEvent
from app.routers.passenger_services import ServiceIn, EventIn, create_service, record_event, get_manifest
from rehearse_passenger_services import snapshot


def main():
    assert engine.dialect.name == 'postgresql' and engine.url.database.startswith('TRACKER_I10_QA_')
    with engine.connect() as connection: columns, before = snapshot(connection)
    migration = (Path(__file__).resolve().parents[1]/'migrations/20261102_passenger_events.up.sql').read_text()
    for _ in range(2):
        with engine.connect() as connection:
            connection.execution_options(isolation_level='AUTOCOMMIT').exec_driver_sql(migration)
    with engine.connect() as connection: assert snapshot(connection, columns)[1] == before
    with engine.connect() as connection:
        outer = connection.begin()
        try:
            with Session(bind=connection, join_transaction_mode='create_savepoint') as db:
                cc = CostCenter(name='Private I10 QA', created_at=datetime.now(timezone.utc)); db.add(cc); db.flush()
                users = [User(username='private-i10-'+uuid.uuid4().hex, full_name='Private QA', password_hash='not-a-password', is_admin=(i==0), is_active=True, created_at=datetime.now(timezone.utc)) for i in range(3)]
                db.add_all(users); db.flush()
                db.add_all([UserCostCenter(user_id=u.id, cost_center_id=cc.id) for u in users[1:]])
                machine = Machine(name='Private I10 vehicle', cost_center_id=cc.id, is_active=True, passenger_capacity=3, created_at=datetime.now(timezone.utc)); db.add(machine); db.flush()
                route = MobileRoute(name='Private I10 route', machine_id=machine.id, waypoints=[], created_by=users[0].id, status='assigned'); db.add(route); db.flush()
                stops = [dict(id=str(uuid.uuid4()), name=label, scheduled_at=at) for label, at in [('Origen','2026-11-02T08:00:00-03:00'), ('Destino','2026-11-02T09:00:00-03:00')]]
                passengers = [dict(id=str(uuid.uuid4()), name='Pasajero ficticio '+str(i), document='QA-'+str(i), boarding_stop_id=stops[0]['id'], alighting_stop_id=stops[1]['id'], seat=i) for i in (1,2,3)]
                service = ServiceIn.model_validate(dict(id=str(uuid.uuid4()), name='Servicio de copia', route_id=str(route.id), driver_user_id=users[1].id, stops=stops, passengers=passengers))
                create_service(service, Response(), db, users[0])
                queued = [EventIn(id=uuid.uuid4(), passenger_id=passengers[p]['id'], kind=kind, expected_version=i, occurred_at=datetime.now(timezone.utc), lat=-33.4, lon=-70.5, accuracy_m=15) for i,(p,kind) in enumerate([(0,'boarded'),(1,'boarded'),(2,'no_show'),(0,'alighted'),(1,'alighted')])]
                for value in queued:
                    result = record_event(service.id, value, Response(), db, users[1])
                    assert record_event(service.id, value, Response(), db, users[1]) == result
                final = get_manifest(service.id, Response(), db, users[1])
                assert final['manifest_version'] == 5 and final['occupied'] == 0
                assert [p['state'] for p in final['passengers']] == ['alighted','alighted','no_show']
                assert db.query(PassengerEvent).filter_by(service_id=service.id).count() == 5
                try: get_manifest(service.id, Response(), db, users[2])
                except HTTPException as exc: assert exc.status_code == 404
                else: raise AssertionError('Driver isolation failed')
                print('POSTGRES_I10_FLOW_OK complete_offline_fifo=True duplicate_receipts=0 final_occupied=0 isolation=True')
        finally: outer.rollback()
    with engine.connect() as connection: assert snapshot(connection, columns)[1] == before
    print('POSTGRES_I10_MIGRATION_OK idempotent=True originals_preserved=True fixtures_rolled_back=True')


if __name__ == '__main__': main()
