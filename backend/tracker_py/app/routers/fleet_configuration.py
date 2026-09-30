"""Tenant-owned device inventory and SIM reminders; no remote device commands."""
from datetime import date
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import Literal
from app.db.session import get_db
from app.models.fleet import Device, DeviceRegistration, Assignment, Asset, Policy, Tenant, now
from app.routers.fleet import Strict, identity, require, owned, audit, asset_out

router = APIRouter(prefix='/v1/configuration', tags=['fleet-configuration'])
SIM_FIELDS = ('phone', 'operator', 'plan_type', 'apn', 'responsible', 'last_recharged_on',
              'next_recharge_on', 'data_expires_on', 'line_review_on', 'reminder_days', 'notes')
REMINDER_LABELS = {'next_recharge_on': 'Recarga programada', 'data_expires_on': 'Vencimiento de datos', 'line_review_on': 'Revisar vigencia de la línea'}


class DeviceDetails(Strict):
    brand: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=100)
    firmware: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=40)
    operator: str | None = Field(None, max_length=100)
    plan_type: Literal['prepaid', 'postpaid', 'iot', 'unknown'] = 'prepaid'
    apn: str | None = Field(None, max_length=100)
    responsible: str | None = Field(None, max_length=200)
    last_recharged_on: date | None = None
    next_recharge_on: date | None = None
    data_expires_on: date | None = None
    line_review_on: date | None = None
    reminder_days: int = Field(7, ge=0, le=90)
    notes: str | None = Field(None, max_length=1000)


class RegisterDevice(DeviceDetails):
    imei: str = Field(pattern=r'^\d{15}$')


class EditDevice(DeviceDetails):
    version: int = Field(ge=1)


def inventory(db, ctx):
    require(ctx, ('manager',))
    today = now().astimezone(ZoneInfo(db.get(Tenant, ctx['tenant_id']).timezone)).date()
    items, reminders = [], []
    for registration in db.query(DeviceRegistration).filter_by(tenant_id=ctx['tenant_id']).order_by(DeviceRegistration.created_at):
        device = db.get(Device, registration.device_id)
        assignment = db.query(Assignment).filter_by(device_id=device.id, tenant_id=ctx['tenant_id'], valid_to=None).one_or_none()
        asset = owned(db, Asset, assignment.asset_id, ctx) if assignment else None
        snapshot = asset_out(db, asset, now()) if asset else None
        item = {key: getattr(registration, key) for key in SIM_FIELDS}
        item.update(id=registration.id, version=registration.version, device_id=device.id, imei=device.imei,
                    brand=device.brand, model=device.model, firmware=device.firmware, protocol=device.protocol,
                    tracking_approved=device.tracking_approved, asset_id=asset.id if asset else None,
                    asset_name=asset.name if asset else None,
                    last_received_at=snapshot['last_position']['received_at'] if snapshot and snapshot['last_position'] else None,
                    signal_state=snapshot['signal_state'] if snapshot else 'no_signal')
        items.append(item)
        for field, title in REMINDER_LABELS.items():
            due = getattr(registration, field)
            if due and (due-today).days <= registration.reminder_days:
                reminders.append({'id': registration.id+':'+field, 'registration_id': registration.id,
                                  'title': title, 'device': device.brand+' '+device.model,
                                  'asset_name': item['asset_name'], 'due_on': due,
                                  'days_remaining': (due-today).days, 'responsible': registration.responsible})
    reminders.sort(key=lambda r: (r['due_on'], r['id']))
    return {'items': items, 'reminders': reminders, 'today': today}


@router.get('')
def configuration(ctx=Depends(identity), db: Session = Depends(get_db)):
    return inventory(db, ctx)


@router.post('/devices')
def register(body: RegisterDevice, ctx=Depends(identity), db: Session = Depends(get_db)):
    require(ctx, ('manager',))
    if not body.brand.strip() or not body.model.strip():
        raise HTTPException(422, 'Marca y modelo son obligatorios')
    # Knowing an existing IMEI never grants access to that device or its history.
    if db.query(Device).filter_by(imei=body.imei).first():
        raise HTTPException(409, 'No se puede registrar este identificador. Solicita revisión al equipo Steps.')
    device = Device(imei=body.imei, brand=body.brand.strip(), model=body.model.strip(), firmware=body.firmware)
    db.add(device)
    try:
        db.flush()
        registration = DeviceRegistration(tenant_id=ctx['tenant_id'], device_id=device.id,
                                          **{k: getattr(body, k) for k in SIM_FIELDS})
        db.add(registration)
        db.flush()
        audit(db, ctx, 'device_registered', {'registration_id': registration.id, 'device_id': device.id})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'No se puede registrar este identificador. Solicita revisión al equipo Steps.')
    return {'id': registration.id}


@router.patch('/devices/{registration_id}')
def edit(registration_id: str, body: EditDevice, ctx=Depends(identity), db: Session = Depends(get_db)):
    require(ctx, ('manager',))
    row = owned(db, DeviceRegistration, registration_id, ctx)
    if row.version != body.version:
        raise HTTPException(409, 'La ficha cambió. Actualiza Configuración antes de editar.')
    if not body.brand.strip() or not body.model.strip():
        raise HTTPException(422, 'Marca y modelo son obligatorios')
    device = db.get(Device, row.device_id)
    changed = [k for k in SIM_FIELDS if getattr(row, k) != getattr(body, k)]
    for key in SIM_FIELDS:
        setattr(row, key, getattr(body, key))
    hardware = (body.brand.strip(), body.model.strip(), body.firmware)
    if hardware != (device.brand, device.model, device.firmware):
        device.tracking_approved = False
    device.brand, device.model, device.firmware = hardware
    row.version += 1
    # SIM values remain private; audit records the changed fields, not phone/APN.
    audit(db, ctx, 'device_configuration_updated', {'registration_id': row.id, 'fields': changed})
    db.commit()
    return {'id': row.id, 'version': row.version}


class AssociateDevice(Strict):
    asset_id: str | None = None
    reason: str = Field(min_length=5, max_length=500)
    version: int = Field(ge=1)


@router.post('/devices/{registration_id}/assignment')
def associate(registration_id: str, body: AssociateDevice, ctx=Depends(identity), db: Session = Depends(get_db)):
    require(ctx, ('manager',))
    registration = owned(db, DeviceRegistration, registration_id, ctx)
    if registration.version != body.version:
        raise HTTPException(409, 'La asociación cambió. Actualiza antes de continuar.')
    db.query(Device).filter_by(id=registration.device_id).with_for_update().one()
    asset = owned(db, Asset, body.asset_id, ctx) if body.asset_id else None
    current = db.query(Assignment).filter_by(device_id=registration.device_id, valid_to=None).one_or_none()
    if current and current.tenant_id != ctx['tenant_id']:
        raise HTTPException(409, 'La instalación requiere revisión del equipo Steps.')
    if current and asset and current.asset_id == asset.id:
        return {'id': registration.id, 'version': registration.version}
    if current:
        policy = db.get(Policy, current.asset_id)
        if policy and policy.armed:
            raise HTTPException(409, 'Desarma la protección del vehículo anterior antes de cambiar el GPS.')
    if asset and db.query(Assignment).filter_by(asset_id=asset.id, valid_to=None).first():
        raise HTTPException(409, 'El vehículo ya tiene un GPS asociado. Desvincúlalo antes de reemplazarlo.')
    boundary = now()
    if current:
        current.valid_to = boundary
        db.flush()
    if asset:
        db.add(Assignment(tenant_id=ctx['tenant_id'], device_id=registration.device_id, asset_id=asset.id, valid_from=boundary))
    registration.version += 1
    audit(db, ctx, 'device_assignment_changed', {'registration_id': registration.id,
          'previous_asset_id': current.asset_id if current else None,
          'asset_id': asset.id if asset else None, 'reason': body.reason}, asset.id if asset else current.asset_id if current else None)
    db.commit()
    return {'id': registration.id, 'version': registration.version}
