"""Supervised starter inhibition. No delayed queue, retry, immediate engine stop or remote start."""
import json, os, socket, time
from datetime import timedelta
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.fleet import Asset, Assignment, Device, DeviceRegistration, Position, Command, Tenant, now
from app.routers.fleet import identity, owned, require, Strict, utc, audit

router=APIRouter(prefix='/v1/assets/{asset_id}/starter-control',tags=['starter-control'])


def relay(message):
    try:
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
            client.settimeout(3)
            client.connect(os.environ.get('TRACKER_STARTER_SOCKET','/run/steps-coban/control.sock'))
            client.sendall(json.dumps(message,separators=(',',':')).encode()+b'\n')
            value=b''
            while not value.endswith(b'\n') and len(value)<4096:
                part=client.recv(4096-len(value))
                if not part:break
                value+=part
            result=json.loads(value)
            if not isinstance(result,dict):raise ValueError()
            return result
    except (OSError,ValueError):
        return {'state':'uncertain','detail':'No se pudo comprobar la entrega al receptor. No se reintentará automáticamente.'}


def assigned(db, asset_id, ctx):
    asset=owned(db,Asset,asset_id,ctx)
    assignment=db.query(Assignment).filter_by(tenant_id=ctx['tenant_id'],asset_id=asset.id,valid_to=None).one_or_none()
    if not assignment:raise HTTPException(409,'El vehículo no tiene un GPS asociado.')
    device=db.get(Device,assignment.device_id)
    registration=db.query(DeviceRegistration).filter_by(tenant_id=ctx['tenant_id'],device_id=device.id).one_or_none()
    return asset,assignment,device,registration


def stopped(db, assignment):
    p=db.query(Position).filter_by(tenant_id=assignment.tenant_id,assignment_id=assignment.id).order_by(Position.recorded_at.desc(),Position.id.desc()).first()
    return bool(p and p.quality=='gps' and utc(p.recorded_at)>=now()-timedelta(seconds=60) and
        utc(p.received_at)>=now()-timedelta(seconds=60) and p.speed_kmh is not None and p.speed_kmh<=0.5 and p.acc is False)


def result(row):
    return {k:getattr(row,k) for k in ('id','asset_id','type','requester','reason','state','result','created_at','confirmed_at','declared_result')}


@router.get('')
def status(asset_id:str,ctx=Depends(identity),db:Session=Depends(get_db)):
    require(ctx,('viewer','operator','manager'))
    asset,assignment,device,registration=assigned(db,asset_id,ctx)
    verified=bool(registration and registration.starter_relay_verified)
    link=relay(dict(operation='status',imei=device.imei)) if verified else {}
    rows=db.query(Command).filter_by(tenant_id=ctx['tenant_id'],asset_id=asset.id).order_by(Command.created_at.desc()).limit(10).all()
    return dict(wiring_verified=verified,connected=link.get('connected') is True,
        can_operate=ctx.get('starter_control') is True and not ctx.get('control_preview'),
        preview=ctx.get('control_preview',False),safe_to_inhibit=stopped(db,assignment),
        commands=[result(r) for r in rows])


class Wiring(Strict):
    starter_circuit:Literal['starter_motor']
    installer:str=Field(min_length=3,max_length=200)
    verified:Literal[True]


@router.post('/wiring')
def wiring(asset_id:str,body:Wiring,ctx=Depends(identity),db:Session=Depends(get_db)):
    require(ctx,('manager',))
    asset,assignment,device,row=assigned(db,asset_id,ctx)
    if not row or device.protocol!='gps103-ascii' or row.receiver_mode!='forward':raise HTTPException(409,'Primero verifica el GPS y su seguimiento.')
    row.starter_relay_verified=True;row.starter_relay_verified_at=now();row.starter_relay_verified_by=body.installer
    audit(db,ctx,'starter_wiring_verified',body.model_dump(),asset.id);db.commit()
    return {'verified':True,'physical_test_pending':True}


class Intention(Strict):
    intention_id:str=Field(min_length=8,max_length=100)
    type:Literal['inhibit_next_start','restore_start']
    reason:str=Field(min_length=5,max_length=500)
    plate_confirmation:str=Field(min_length=1,max_length=40)
    present:Literal[True]
    engine_off:Literal[True]


@router.post('/commands')
def request_command(asset_id:str,body:Intention,ctx=Depends(identity),db:Session=Depends(get_db)):
    require(ctx,('operator','manager'))
    asset,assignment,device,registration=assigned(db,asset_id,ctx)
    if not ctx.get('starter_control') or ctx.get('control_preview'):raise HTTPException(403,'Este perfil no puede emitir órdenes físicas.')
    authenticated=ctx.get('actuator_auth_at')
    if not isinstance(authenticated,(int,float)) or not 0<=time.time()-authenticated<=60:raise HTTPException(403,'Confirma nuevamente tu contraseña para esta operación.')
    if body.plate_confirmation.strip().upper()!=str(asset.plate or '').strip().upper():raise HTTPException(422,'La patente de confirmación no coincide.')
    if not registration or not registration.starter_relay_verified or registration.receiver_mode!='forward' or not device.tracking_approved:
        raise HTTPException(409,'La instalación de bloqueo de arranque no está verificada.')
    previous=db.query(Command).filter_by(tenant_id=ctx['tenant_id'],intention_id=body.intention_id).one_or_none()
    if previous:
        if previous.asset_id!=asset.id or previous.type!=body.type or previous.requester!=ctx['user_id']:raise HTTPException(409,'La intención ya existe con otros datos.')
        return result(previous)
    if body.type=='inhibit_next_start' and not stopped(db,assignment):
        raise HTTPException(409,'Para bloquear se requiere GPS válido de menos de un minuto, velocidad cero y ACC apagado. No se deja una orden pendiente.')
    latest=db.query(Command).filter_by(tenant_id=ctx['tenant_id'],asset_id=asset.id).order_by(Command.created_at.desc()).first()
    if body.type=='inhibit_next_start' and latest and latest.state in ('dispatching','sent_unconfirmed','uncertain'):
        raise HTTPException(409,'Primero comprueba la orden anterior o restituye el arranque. No repetimos bloqueos sin resultado confirmado.')
    tenant=db.get(Tenant,ctx['tenant_id'])
    message=dict(operation='dispatch',imei=device.imei,device_id=device.id,issuer=tenant.issuer,
        company_id=tenant.company_id,action=body.type,deadline=time.time()+8)
    # Commit the intention before touching the socket: an interrupted HTTP request
    # may be uncertain but can never be resent by repeating the same intention.
    row=Command(tenant_id=ctx['tenant_id'],asset_id=asset.id,device_id=device.id,assignment_id=assignment.id,
        intention_id=body.intention_id,type=body.type,requester=ctx['user_id'],reason=body.reason,
        state='dispatching',result='Entrega en curso; resultado físico sin confirmar.')
    db.add(row);db.flush();message['command_id']=row.id
    audit(db,ctx,'starter_command_requested',dict(command_id=row.id,type=body.type,reason=body.reason),asset.id);db.commit()
    # Reacquire the tenant lock after the durable receipt, and recheck ownership.
    db.query(Tenant).filter_by(id=ctx['tenant_id']).with_for_update().one()
    _,current,current_device,current_registration=assigned(db,asset_id,ctx)
    if current.id!=row.assignment_id or not current_registration or not current_registration.starter_relay_verified or current_registration.receiver_mode!='forward' or not current_device.tracking_approved:
        delivery={'state':'failed','detail':'La asociación o instalación cambió; no se envió una orden.'}
    else:delivery=relay(message)
    row.state=delivery.get('state') if delivery.get('state') in ('sent_unconfirmed','failed','uncertain') else 'uncertain'
    row.result=str(delivery.get('detail') or 'Resultado físico sin confirmar.')[:500]
    audit(db,ctx,'starter_command_delivery',dict(command_id=row.id,state=row.state),asset.id);db.commit()
    return result(row)


class Confirmation(Strict):
    observed:Literal['blocked','restored','not_observed']
    present:Literal[True]
    reason:str=Field(min_length=5,max_length=500)


@router.post('/commands/{command_id}/confirm')
def confirm(asset_id:str,command_id:str,body:Confirmation,ctx=Depends(identity),db:Session=Depends(get_db)):
    require(ctx,('operator','manager'))
    owned(db,Asset,asset_id,ctx);row=owned(db,Command,command_id,ctx)
    if not ctx.get('starter_control') or ctx.get('control_preview') or row.asset_id!=asset_id:raise HTTPException(403,'Permiso insuficiente')
    if row.state not in ('sent_unconfirmed','uncertain','dispatching'):raise HTTPException(409,'Esta orden no admite confirmación de terreno.')
    if body.observed!='not_observed' and body.observed!=('blocked' if row.type=='inhibit_next_start' else 'restored'):raise HTTPException(422,'El resultado no corresponde a esta orden.')
    row.declared_result=body.observed;row.confirmed_at=now();row.state='confirmed' if body.observed!='not_observed' else 'uncertain'
    row.result='Comprobación de terreno registrada por el usuario; no es una lectura eléctrica del relé.'
    audit(db,ctx,'starter_physical_observation',dict(command_id=row.id,**body.model_dump()),asset_id);db.commit();return result(row)
