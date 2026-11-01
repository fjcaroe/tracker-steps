"""Private receiver polling and tenant-scoped commissioning over the existing API."""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import AwareDatetime, Field
from sqlalchemy.orm import Session
from typing import Literal
from app.db.session import get_db
from app.models.fleet import Tenant, Device, DeviceRegistration, Assignment, now
from app.routers.fleet import Strict, identity, require, utc, audit, owned

router=APIRouter(prefix='/v1',tags=['receiver-commissioning'])


def receiver_info(db,ctx):
    tenant=db.get(Tenant,ctx['tenant_id'])
    supported=tenant.issuer=='CERRO_EL_PLOMO'
    return {'supported':supported,'online':bool(supported and tenant.receiver_seen_at and utc(tenant.receiver_seen_at)>now()-timedelta(seconds=30)),
            'last_seen_at':tenant.receiver_seen_at if supported else None,'release':tenant.receiver_release if supported else None,
            'host':'35.222.25.110' if supported else None,'port':5001 if supported else None,'transport':'TCP','protocol':'gps103-ascii'}


def diagnostic(row):
    return {'mode':row.receiver_mode,'last_seen_at':row.receiver_seen_at,'fix_at':row.receiver_fix_at,
            'fix_received_at':row.receiver_fix_received_at,'lat':row.receiver_lat,'lon':row.receiver_lon,
            'speed_kmh':row.receiver_speed,'last_error':row.receiver_error,'pending':row.receiver_pending}


class Observation(Strict):
    imei: str = Field(pattern=r'^\d{15}$')
    last_seen_at: AwareDatetime | None = None
    fix_at: AwareDatetime | None = None
    fix_received_at: AwareDatetime | None = None
    lat: float | None = Field(None,ge=-90,le=90,allow_inf_nan=False)
    lon: float | None = Field(None,ge=-180,le=180,allow_inf_nan=False)
    speed_kmh: float | None = Field(None,ge=0,le=300,allow_inf_nan=False)
    error: Literal['decode_rejected','no_valid_gps','api_retry','queue_full'] | None = None
    pending: int = Field(0,ge=0,le=20000)


class Poll(Strict):
    release: str = Field(min_length=1,max_length=80)
    observations: list[Observation] = Field(default_factory=list,max_length=500)


@router.post('/receiver/poll')
def poll(body: Poll,ctx=Depends(identity),db: Session=Depends(get_db)):
    require(ctx,('ingestor',))
    tenant=db.get(Tenant,ctx['tenant_id'])
    if tenant.issuer!='CERRO_EL_PLOMO':raise HTTPException(403,'Receptor no autorizado para este origen')
    tenant.receiver_seen_at=now();tenant.receiver_release=body.release
    rows=db.query(DeviceRegistration).filter_by(tenant_id=tenant.id).with_for_update().all()
    by_imei={db.get(Device,r.device_id).imei:r for r in rows}
    for observation in body.observations:
        row=by_imei.get(observation.imei)
        if row is None or row.receiver_mode=='disabled':continue
        if row.receiver_started_at and (not observation.last_seen_at or observation.last_seen_at<utc(row.receiver_started_at)):continue
        for stamp in (observation.last_seen_at,observation.fix_at,observation.fix_received_at):
            if stamp and stamp>now()+timedelta(minutes=5):raise HTTPException(422,'Hora de diagnóstico futura')
        if observation.last_seen_at and (not row.receiver_seen_at or observation.last_seen_at>=utc(row.receiver_seen_at)):
            row.receiver_seen_at=observation.last_seen_at;row.receiver_error=observation.error;row.receiver_pending=observation.pending
        if observation.fix_at and observation.fix_received_at and observation.lat is not None and observation.lon is not None:
            if (not row.receiver_started_at or observation.fix_received_at>=utc(row.receiver_started_at)) and (not row.receiver_fix_at or observation.fix_at>=utc(row.receiver_fix_at)):
                row.receiver_fix_at=observation.fix_at;row.receiver_fix_received_at=observation.fix_received_at
                row.receiver_lat=observation.lat;row.receiver_lon=observation.lon;row.receiver_speed=observation.speed_kmh
    devices=[]
    for row in rows:
        if row.receiver_mode=='disabled':continue
        device=db.get(Device,row.device_id)
        if device.protocol!='gps103-ascii':continue
        assignment=db.query(Assignment).filter_by(tenant_id=tenant.id,device_id=device.id,valid_to=None).one_or_none()
        mode=row.receiver_mode if assignment else 'capture'
        devices.append({'imei':device.imei,'issuer':tenant.issuer,'company_id':tenant.company_id,'device_id':device.id,'mode':mode})
    db.commit()
    return {'devices':devices,'generated_at':now()}


class Commissioning(Strict):
    mode: Literal['disabled','capture','forward']
    protocol: Literal['gps103-ascii'] = 'gps103-ascii'
    version: int = Field(ge=1)
    reason: str = Field(min_length=5,max_length=500)
    verified: bool = False


def locked_registration(db,registration_id,ctx):
    row=db.query(DeviceRegistration).filter_by(id=registration_id,tenant_id=ctx['tenant_id']).with_for_update().one_or_none()
    if row is None:raise HTTPException(404,'GPS no encontrado')
    return row


@router.post('/configuration/devices/{registration_id}/commissioning')
def commission(registration_id: str,body: Commissioning,ctx=Depends(identity),db: Session=Depends(get_db)):
    require(ctx,('manager',))
    if db.get(Tenant,ctx['tenant_id']).issuer!='CERRO_EL_PLOMO':raise HTTPException(403,'La recepción Coban está habilitada para Cerro productivo')
    row=locked_registration(db,registration_id,ctx)
    if row.version!=body.version:raise HTTPException(409,'La ficha cambió. Actualiza antes de configurar recepción.')
    device=db.query(Device).filter_by(id=row.device_id).with_for_update().one()
    if body.mode=='forward':
        assignment=db.query(Assignment).filter_by(device_id=device.id,tenant_id=ctx['tenant_id'],valid_to=None).one_or_none()
        if not assignment:raise HTTPException(422,'Asocia primero el GPS a su vehículo.')
        tenant=db.get(Tenant,ctx['tenant_id'])
        if not tenant.receiver_seen_at or utc(tenant.receiver_seen_at)<now()-timedelta(seconds=30):raise HTTPException(422,'El receptor no está comunicando. Actualiza el diagnóstico.')
        if (row.receiver_mode not in ('capture','forward') or not row.receiver_fix_at or not row.receiver_fix_received_at or
            utc(row.receiver_fix_at)<now()-timedelta(minutes=5) or utc(row.receiver_fix_received_at)<now()-timedelta(minutes=5) or
            utc(row.receiver_fix_at)<utc(assignment.valid_from) or utc(row.receiver_fix_received_at)<utc(assignment.valid_from)):
            raise HTTPException(422,'Falta una posición GPS reciente recibida después de asociar el vehículo. Habilita recepción de prueba.')
        if not body.verified:raise HTTPException(422,'Confirma que revisaste la identidad, ubicación y hora del equipo físico.')
    previous=row.receiver_mode
    if body.mode=='capture':
        row.receiver_started_at=now();row.receiver_fix_at=None;row.receiver_fix_received_at=None
        row.receiver_lat=None;row.receiver_lon=None;row.receiver_speed=None;row.receiver_error=None;row.receiver_seen_at=None
    row.receiver_mode=body.mode;device.protocol=body.protocol
    device.tracking_approved=body.mode=='forward';row.version+=1
    audit(db,ctx,'receiver_mode_changed',{'registration_id':row.id,'previous':previous,'mode':row.receiver_mode,'reason':body.reason,'physical_review_confirmed':body.verified})
    db.commit()
    return {'id':row.id,'version':row.version,'mode':row.receiver_mode}
