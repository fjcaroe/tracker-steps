"""Loopback-only I10 browser fixture; refuses real databases and uses a QA JWT."""
import json
import os
from pathlib import Path
import uuid
from datetime import datetime,timezone
import uvicorn
from fastapi import Response
from app.main import app
from app.db.session import engine, SessionLocal
from app.core.security import create_access_token
from app.models.users import User, UserCostCenter
from app.models.cost_centers import CostCenter
from app.models.machines import Machine
from app.models.mobile import MobileRoute
from app.routers.passenger_services import ServiceIn, create_service

assert engine.url.database.startswith('TRACKER_I10_UI_QA_')
assert os.environ['JWT_SECRET']=='private-i10-browser-copy-only'
with SessionLocal() as db:
    cc=CostCenter(name='Copia I10',created_at=datetime.now(timezone.utc));db.add(cc);db.flush()
    user=User(username='private-i10-browser-'+uuid.uuid4().hex,full_name='Conductor de copia',password_hash='not-a-password',is_admin=True,is_active=True,created_at=datetime.now(timezone.utc));db.add(user);db.flush()
    db.add(UserCostCenter(user_id=user.id,cost_center_id=cc.id))
    machine=Machine(name='Bus de copia',plate='QA0046',cost_center_id=cc.id,is_active=True,passenger_capacity=3,created_at=datetime.now(timezone.utc));db.add(machine);db.flush()
    route=MobileRoute(name='Ruta de copia',machine_id=machine.id,waypoints=[],created_by=user.id,status='assigned');db.add(route);db.flush()
    stops=[dict(id=str(uuid.uuid4()),name=label,scheduled_at=at) for label,at in [('Origen','2026-11-02T08:00:00-03:00'),('Destino','2026-11-02T09:00:00-03:00')]]
    passengers=[dict(id=str(uuid.uuid4()),name='Pasajero ficticio '+str(i),document='QA-'+str(i),boarding_stop_id=stops[0]['id'],alighting_stop_id=stops[1]['id'],seat=i) for i in (1,2,3)]
    service=ServiceIn.model_validate(dict(id=str(uuid.uuid4()),name='Servicio de copia',route_id=str(route.id),driver_user_id=user.id,stops=stops,passengers=passengers))
    result=create_service(service,Response(),db,user)
    proof=Path(os.environ['PASSENGER_UI_PROOF']);proof.write_text(json.dumps(dict(token=create_access_token({'sub':str(user.id)}),user_id=user.id,service=result),default=str));proof.chmod(0o600)
print('PASSENGER_COPY_SERVER_READY',flush=True)
uvicorn.run(app,host='127.0.0.1',port=18012,log_level='warning')
