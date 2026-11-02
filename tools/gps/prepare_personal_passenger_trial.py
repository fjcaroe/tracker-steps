"""Explicitly authorized four fictional passengers, Development database only."""
import argparse,json,uuid
from pathlib import Path
from fastapi import Response
from app.main import app  # noqa: F401
from app.db.session import engine,SessionLocal
from app.models.users import User
from app.models.fleet import Tenant
from app.models.mobile import MobileRoute
from app.models.machines import Machine
from app.routers.passenger_services import ServiceIn,create_service,get_manifest
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('plan',type=Path);parser.add_argument('ids',type=Path);args=parser.parse_args()
assert engine.url.database=='tracker_steps_development' or engine.url.database.startswith('PERSONAL_JOURNEY_QA_')
plan=json.loads(args.plan.read_text());ids=json.loads(args.ids.read_text());trial=plan['passenger_trial']
with SessionLocal() as db:
 user=db.query(User).filter_by(username=trial['driver_username'],is_active=True).one()
 machine=db.get(Machine,ids['machine_id']);assert machine.passenger_capacity==4 and machine.external_id==plan['machine_external_id']
 route=db.get(MobileRoute,uuid.UUID(trial['route_id']))
 if route is None:
  route=MobileRoute(id=uuid.UUID(trial['route_id']),name='Servicio de prueba — sin recorrido programado',machine_id=machine.id,waypoints=[],created_by=user.id,status='assigned',note='Pasajeros ficticios autorizados para pruebas personales en Desarrollo. No es un traslado real.');db.add(route);db.commit()
 assert route.machine_id==machine.id and route.created_by==user.id
 body=ServiceIn.model_validate(dict(id=trial['id'],name='PRUEBA · C3 · 4 pasajeros ficticios',route_id=trial['route_id'],driver_user_id=user.id,stops=trial['stops'],passengers=trial['passengers']))
 result=create_service(body,Response(),db,user);assert create_service(body,Response(),db,user)['id']==result['id']
 manifest=get_manifest(body.id,Response(),db,user);assert len(manifest['passengers'])==4 and manifest['capacity']==4
 print('PERSONAL_PASSENGER_TRIAL_READY four_fictional_passengers=True assigned_native_user=True idempotent=True')
