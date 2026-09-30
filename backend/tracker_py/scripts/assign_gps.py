"""Explicit commissioning; no implicit migration of legacy devices or history.

Pass a JSON file with issuer, company_id, asset_source_id, imei, brand, model,
firmware, protocol and valid_from (timezone required). Default tracking approval
is false. No physical-control capability can be enabled using this script.
"""
import json
import sys
from datetime import datetime
from sqlalchemy import or_
from app.db.session import SessionLocal
from app.models.fleet import Tenant, Asset, Device, Assignment, Audit, now

data = json.load(open(sys.argv[1], encoding='utf-8'))
boundary = datetime.fromisoformat(data['valid_from'].replace('Z', '+00:00'))
if boundary.tzinfo is None or boundary > now():
    raise ValueError('valid_from requires timezone and cannot be in the future')
with SessionLocal.begin() as db:
    tenant = db.query(Tenant).filter_by(issuer=data['issuer'], company_id=data['company_id']).with_for_update().one()
    asset = db.query(Asset).filter_by(tenant_id=tenant.id, source_id=data['asset_source_id']).with_for_update().one()
    device = db.query(Device).filter_by(imei=data['imei']).with_for_update().one_or_none()
    if not device:
        device = Device(**{key: data.get(key) for key in ('imei', 'brand', 'model', 'firmware', 'protocol')})
        db.add(device)
        db.flush()
    # Reassignment is intentionally separate: operator must close previous
    # interval after checking it, never silently steal an active installation.
    if db.query(Assignment).filter(or_(Assignment.device_id == device.id, Assignment.asset_id == asset.id), Assignment.valid_to.is_(None)).first():
        raise ValueError('An active assignment exists; reconcile it explicitly first')
    assignment = Assignment(tenant_id=tenant.id, device_id=device.id, asset_id=asset.id, valid_from=boundary)
    db.add(assignment)
    db.flush()
    db.add(Audit(tenant_id=tenant.id, asset_id=asset.id, actor='installer:server-cli', action='device_assigned', detail={'assignment_id': assignment.id, 'device_id': device.id, 'control': 'not_approved'}))
    print(json.dumps({'asset_id': asset.id, 'device_id': device.id, 'assignment_id': assignment.id}))
