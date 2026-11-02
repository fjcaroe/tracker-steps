"""Loopback server for the prepared destination copy; reuses its real account."""
import os,json
from pathlib import Path
import uvicorn
from app.main import app
from app.db.session import engine,SessionLocal
from app.core.security import create_access_token
from app.models.users import User
from app.models.fleet import Tenant
from app.models.machines import Machine
assert engine.url.database.startswith('PERSONAL_JOURNEY_QA_') and os.environ['JWT_SECRET']=='private-journey-copy-only'
with SessionLocal() as db:
 tenant=db.query(Tenant).filter_by(issuer='LAB_TAREAS',company_id=1).one()
 user=db.query(User).filter_by(username='odoo-'+tenant.id.replace('-','')[:8]+'-6',is_active=True).one()
 machine=db.query(Machine).one();assert machine.passenger_capacity==4 and machine.fuel_consumption_unit=='kmpl'
 proof=Path('/tmp/journey-ui-proof-20261102.json');proof.write_text(json.dumps(dict(token=create_access_token({'sub':str(user.id)}),machine_id=machine.id)));proof.chmod(0o600)
print('PERSONAL_JOURNEY_REVIEW_SERVER_READY',flush=True)
uvicorn.run(app,host='127.0.0.1',port=18013,log_level='warning')
