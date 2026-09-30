"""Tenant-scoped GPS API; Odoo signs short-lived server-to-server identities."""
import json
import os
import math
from uuid import uuid4
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from jose import jwt, JWTError
from pydantic import BaseModel, Field, ConfigDict, AwareDatetime
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.core.security import oauth2_scheme
from app.db.session import get_db
from app.models.fleet import Tenant, Asset, Device, Assignment, Position, Policy, Incident, Audit, Preference, Command, now

router = APIRouter(prefix='/v1', tags=['fleet-protection'])


def bridge_keys():
    if os.environ.get('TRACKER_BRIDGE_KEYS'):
        return json.loads(os.environ['TRACKER_BRIDGE_KEYS'])
    path = Path(os.environ.get('TRACKER_BRIDGE_KEYS_FILE', '/etc/tracker-bridge-keys.json'))
    return json.loads(path.read_text()) if path.exists() else {}


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def identity(token=Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        issuer = jwt.get_unverified_claims(token).get('iss')
        key = bridge_keys().get(issuer)
        if not key:
            raise ValueError('Unknown issuer')
        claims = jwt.decode(token, key, algorithms=['HS256'], audience='steps-tracker-v1', issuer=issuer,
                            options={'require_exp': True, 'require_sub': True, 'require_iat': True})
        if claims['exp'] - claims['iat'] > 90 or claims['iat'] > now().timestamp() + 5:
            raise ValueError('Invalid lifetime')
        # Serialize this tenant's commits with its change-feed readers. A cursor
        # cannot advance past an older, still-uncommitted audit event.
        tenant = db.query(Tenant).filter_by(issuer=issuer, company_id=int(claims['company_id'])).with_for_update().one_or_none()
        if not tenant or claims.get('role') not in ('viewer', 'operator', 'manager', 'ingestor'):
            raise ValueError('Unmapped identity')
        return {'tenant_id': tenant.id, 'user_id': claims['sub'], 'role': claims['role'], 'tenant': tenant.name}
    except (JWTError, ValueError, KeyError, TypeError):
        raise HTTPException(401, 'Identidad o compañía no autorizada')


def require(ctx, roles):
    if ctx['role'] not in roles:
        raise HTTPException(403, 'Permiso insuficiente')


def owned(db, model, object_id, ctx):
    obj = db.query(model).filter_by(id=object_id, tenant_id=ctx['tenant_id']).one_or_none()
    if obj is None:
        raise HTTPException(404, 'Registro no encontrado')
    return obj


def audit(db, ctx, action, detail, asset_id=None, incident_id=None):
    db.add(Audit(tenant_id=ctx['tenant_id'], actor=ctx['user_id'], action=action,
                 detail=detail, asset_id=asset_id, incident_id=incident_id))


def position_out(p):
    return None if p is None else {k: getattr(p, k) for k in ('id', 'recorded_at', 'received_at', 'lat', 'lon', 'speed_kmh', 'quality', 'acc', 'external_power')}


def asset_out(db, a, at):
    assignment = db.query(Assignment).filter_by(asset_id=a.id, tenant_id=a.tenant_id, valid_to=None).first()
    device = db.get(Device, assignment.device_id) if assignment else None
    # The old device's last point stays in history, never becomes a new assignment's current state.
    p = db.query(Position).filter_by(tenant_id=a.tenant_id, asset_id=a.id, assignment_id=assignment.id).order_by(Position.recorded_at.desc(), Position.id.desc()).first() if assignment else None
    fresh = bool(p and (at-utc(p.received_at)).total_seconds() <= device.freshness_seconds)
    recent_fix = bool(p and (at-utc(p.recorded_at)).total_seconds() <= device.freshness_seconds and p.quality == 'gps')
    policy = db.get(Policy, a.id)
    incident = db.query(Incident).filter_by(tenant_id=a.tenant_id, asset_id=a.id).filter(Incident.state != 'closed').first()
    return {**{k: getattr(a, k) for k in ('name', 'plate', 'type', 'cost_center', 'responsible', 'created_at')},
            'asset_id': a.id, 'linked_to_odoo': a.source_id.startswith('odoo:'), 'last_position': position_out(p),
            'signal_state': 'received' if fresh else 'stale' if p else 'no_signal',
            'motion_state': ('moving' if p.speed_kmh > 2 else 'stationary') if fresh and recent_fix and p.speed_kmh is not None else 'unknown',
            'position_stale': not recent_fix,
            'protection_state': 'incident_open' if incident else 'armed' if policy and policy.armed else 'disarmed',
            'device': {'model': device.model, 'brand': device.brand, 'firmware': device.firmware, 'protocol': device.protocol} if device else None,
            'capabilities': {'tracking': 'approved' if device and device.tracking_approved else 'not_approved', 'remote_start_inhibit': 'not_approved'}}


@router.get('/fleet/snapshot')
def snapshot(q: str = '', type: str = '', cost_center: str = '', motion: str = '', signal: str = '', protection: str = '', gps: str = '',
             after: str = '', limit: int = Query(200, ge=1, le=500), ctx=Depends(identity), db: Session = Depends(get_db)):
    require(ctx, ('viewer', 'operator', 'manager'))
    rows = [asset_out(db, a, now()) for a in db.query(Asset).filter_by(tenant_id=ctx['tenant_id']).order_by(Asset.id)]
    rows = [r for r in rows if (not q or q.casefold() in (r['name']+' '+(r['plate'] or '')).casefold())
            and (not type or r['type'] == type) and (not cost_center or r['cost_center'] == cost_center)
            and (not motion or r['motion_state'] == motion) and (not signal or r['signal_state'] == signal)
            and (not protection or r['protection_state'] == protection) and (not gps or (r['device'] or {}).get('model') == gps)]
    page = [r for r in rows if r['asset_id'] > after][:limit + 1]
    return {'items': page[:limit], 'total': len(rows), 'next_cursor': page[limit-1]['asset_id'] if len(page) > limit else None,
            'counts': {key: sum(r['signal_state'] == key for r in rows) for key in ('received', 'stale', 'no_signal')},
            'tenant': ctx['tenant'], 'tenant_id': ctx['tenant_id'], 'user_id': ctx['user_id'], 'role': ctx['role'], 'generated_at': now()}


@router.get('/asset-sources')
def asset_sources(after: str = '', limit: int = Query(200, ge=1, le=500), ctx=Depends(identity), db: Session = Depends(get_db)):
    """Correspondencia activo -> origen (p. ej. odoo:fleet.vehicle:<id>) para el puente servidor a servidor.

    Solo rol manager y solo el cliente de la identidad firmada. Fuera del prefijo ``assets/`` a propósito:
    el proxy del navegador en Odoo nunca llega a esta ruta.
    """
    require(ctx, ('manager',))
    query = db.query(Asset).filter(Asset.tenant_id == ctx['tenant_id'])
    if after:
        query = query.filter(Asset.id > after)
    rows = query.order_by(Asset.id).limit(limit + 1).all()
    page = rows[:limit]
    return {'items': [{'asset_id': a.id, 'source_id': a.source_id, 'name': a.name, 'plate': a.plate} for a in page],
            'next_cursor': page[-1].id if len(rows) > limit else None}


@router.get('/assets/{asset_id}')
def asset_detail(asset_id: str, ctx=Depends(identity), db: Session = Depends(get_db)):
    require(ctx, ('viewer', 'operator', 'manager'))
    return asset_out(db, owned(db, Asset, asset_id, ctx), now())


@router.get('/assets/{asset_id}/positions')
def positions(asset_id: str, before: str = '', limit: int = Query(100, ge=1, le=500), current_assignment: bool = False, since: AwareDatetime | None = None, ctx=Depends(identity), db: Session = Depends(get_db)):
    require(ctx, ('viewer', 'operator', 'manager'))
    owned(db, Asset, asset_id, ctx)
    query = db.query(Position).filter_by(tenant_id=ctx['tenant_id'], asset_id=asset_id)
    if current_assignment:
        assignment = db.query(Assignment).filter_by(tenant_id=ctx['tenant_id'], asset_id=asset_id, valid_to=None).first()
        if not assignment:
            return {'items': [], 'next_cursor': None}
        query = query.filter(Position.assignment_id == assignment.id)
    if since:
        query = query.filter(Position.recorded_at >= since)
    if before:
        anchor = query.filter_by(id=before).one_or_none()
        if not anchor:
            raise HTTPException(400, 'Cursor inválido')
        query = query.filter(or_(Position.recorded_at < anchor.recorded_at, (Position.recorded_at == anchor.recorded_at) & (Position.id < anchor.id)))
    rows = query.order_by(Position.recorded_at.desc(), Position.id.desc()).limit(limit + 1).all()
    return {'items': [position_out(p) for p in rows[:limit]], 'next_cursor': rows[limit-1].id if len(rows) > limit else None}


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class AssetInput(Strict):
    source_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    plate: str | None = Field(None, max_length=40)
    type: str = Field('vehicle', max_length=50)
    cost_center: str | None = Field(None, max_length=200)
    responsible: str | None = Field(None, max_length=200)
    created_at: AwareDatetime | None = None


class AssetDetails(Strict):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    plate: str | None = Field(None, max_length=40)
    type: str = Field('vehicle', min_length=1, max_length=50)
    cost_center: str | None = Field(None, max_length=200)
    responsible: str | None = Field(None, max_length=200)


@router.post('/assets')
def create_asset(body: AssetDetails, ctx=Depends(identity), db: Session = Depends(get_db)):
    require(ctx, ('manager',))
    row = Asset(tenant_id=ctx['tenant_id'], source_id='manual:'+str(uuid4()), **body.model_dump())
    db.add(row)
    db.flush()
    audit(db, ctx, 'asset_created', {'name': row.name, 'type': row.type}, row.id)
    db.commit()
    return {'asset_id': row.id}


@router.patch('/assets/{asset_id}')
def edit_asset(asset_id: str, body: AssetDetails, ctx=Depends(identity), db: Session = Depends(get_db)):
    require(ctx, ('manager',))
    row = owned(db, Asset, asset_id, ctx)
    changes = {k: {'before': getattr(row, k), 'after': v} for k, v in body.model_dump().items() if getattr(row, k) != v}
    for k, v in body.model_dump().items():
        setattr(row, k, v)
    audit(db, ctx, 'asset_updated', changes, row.id)
    db.commit()
    return {'asset_id': row.id}


@router.put('/assets')
def upsert_asset(body: AssetInput, ctx=Depends(identity), db: Session = Depends(get_db)):
    require(ctx, ('manager',))
    row = db.query(Asset).filter_by(tenant_id=ctx['tenant_id'], source_id=body.source_id).one_or_none()
    if not row:
        row = Asset(tenant_id=ctx['tenant_id'], **body.model_dump(exclude_none=True))
        db.add(row)
    else:
        for k, v in body.model_dump(exclude={'created_at'}).items():
            setattr(row, k, v)
    db.flush()
    audit(db, ctx, 'asset_upsert', {'source_id': body.source_id}, row.id)
    db.commit()
    return {'asset_id': row.id}


COLUMNS = {'name', 'motion_state', 'signal_state', 'protection_state', 'type', 'created_at', 'device', 'cost_center', 'responsible', 'acc'}
class ViewInput(Strict):
    schema_version: Literal[1] = 1
    columns: list[str] = Field(max_length=10)
    filters: dict[str, str] = Field(default_factory=dict)
    sort: Literal['name', 'created_at', 'signal_state'] = 'name'


@router.get('/view-preferences/{view_key}')
def get_preference(view_key: str, ctx=Depends(identity), db: Session = Depends(get_db)):
    require(ctx, ('viewer', 'operator', 'manager'))
    row = db.get(Preference, (ctx['tenant_id'], ctx['user_id'], view_key))
    return row.value if row else None


@router.put('/view-preferences/{view_key}')
def put_preference(view_key: str, body: ViewInput, ctx=Depends(identity), db: Session = Depends(get_db)):
    require(ctx, ('viewer', 'operator', 'manager'))
    if len(view_key) > 80 or not set(body.columns) <= COLUMNS or not set(body.filters) <= {'q', 'type', 'cost_center', 'motion', 'signal', 'protection', 'gps'} or any(len(v) > 200 for v in body.filters.values()):
        raise HTTPException(422, 'Preferencia no permitida')
    db.merge(Preference(tenant_id=ctx['tenant_id'], user_id=ctx['user_id'], view_key=view_key, value=body.model_dump()))
    db.commit()
    return body


class Zone(Strict):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radius_m: float = Field(ge=10, le=100000)


class PolicyInput(Strict):
    asset_id: str
    armed: bool
    version: int = Field(ge=0)
    reason: str = Field(min_length=5, max_length=2000)
    contacts: list[str] = Field(default_factory=list, max_length=10)
    allowed_hours_utc: list[int] = Field(default_factory=list, max_length=24)
    zone: Zone | None = None


@router.get('/security/policies')
def policies(ctx=Depends(identity), db: Session = Depends(get_db)):
    require(ctx, ('viewer', 'operator', 'manager'))
    return [{'asset_id': r.asset_id, 'armed': r.armed, 'version': r.version, 'contacts': r.contacts,
             'zone': r.zone, 'allowed_hours_utc': r.allowed_hours_utc} for r in db.query(Policy).filter_by(tenant_id=ctx['tenant_id'])]


@router.put('/security/policies')
def policy_write(body: PolicyInput, ctx=Depends(identity), db: Session = Depends(get_db)):
    require(ctx, ('manager',))
    # The asset lock serializes first creation and all subsequent policy/incident changes.
    owned(db, Asset, body.asset_id, ctx)
    db.query(Asset).filter_by(id=body.asset_id).with_for_update().one()
    row = db.get(Policy, body.asset_id)
    if (row.version if row else 0) != body.version:
        raise HTTPException(409, 'La política cambió; vuelve a cargar')
    if any(h < 0 or h > 23 for h in body.allowed_hours_utc) or any(len(c) > 200 for c in body.contacts):
        raise HTTPException(422, 'Horario o contacto inválido')
    if not row:
        row = Policy(asset_id=body.asset_id, tenant_id=ctx['tenant_id'])
        db.add(row)
    for k in ('armed', 'contacts', 'allowed_hours_utc', 'zone'):
        setattr(row, k, body.model_dump()[k])
    row.version = body.version + 1
    row.updated_at = now()
    audit(db, ctx, 'policy_changed', body.model_dump(), body.asset_id)
    db.commit()
    return {'version': row.version}


def incident_out(db, row, detail=False):
    value = {k: getattr(row, k) for k in ('id', 'asset_id', 'type', 'severity', 'state', 'responsible', 'created_at', 'updated_at')}
    if detail:
        value['timeline'] = [{k: getattr(a, k) for k in ('id', 'actor', 'action', 'detail', 'created_at')}
                             for a in db.query(Audit).filter_by(tenant_id=row.tenant_id, incident_id=row.id).order_by(Audit.created_at, Audit.id)]
    return value


def raise_incident(db, ctx, asset_id, kind, evidence):
    db.query(Asset).filter_by(id=asset_id, tenant_id=ctx['tenant_id']).with_for_update().one()
    row = db.query(Incident).filter_by(tenant_id=ctx['tenant_id'], asset_id=asset_id, type=kind).filter(Incident.state != 'closed').first()
    if not row:
        row = Incident(tenant_id=ctx['tenant_id'], asset_id=asset_id, type=kind, severity='high' if kind in ('sos', 'external_power_lost') else 'medium')
        db.add(row)
        db.flush()
        audit(db, ctx, 'incident_opened', evidence, asset_id, row.id)
        audit(db, ctx, 'notification_pending', {'channel': 'in_app', 'delivery': 'available_in_inbox', 'external_delivery': 'not_configured'}, asset_id, row.id)
    return row


class IncidentInput(Strict):
    asset_id: str
    type: Literal['suspected_movement', 'external_power_lost', 'communication_failure', 'sos', 'outside_zone', 'acc_outside_schedule', 'manual']
    reason: str = Field(min_length=5, max_length=2000)


@router.get('/security/incidents')
def incidents(after: str = '', limit: int = Query(100, ge=1, le=500), ctx=Depends(identity), db: Session = Depends(get_db)):
    require(ctx, ('viewer', 'operator', 'manager'))
    rows = db.query(Incident).filter_by(tenant_id=ctx['tenant_id']).filter(Incident.id > after).order_by(Incident.id).limit(limit + 1).all()
    return {'items': [incident_out(db, r) for r in rows[:limit]], 'next_cursor': rows[limit-1].id if len(rows) > limit else None}


@router.post('/security/incidents')
def incident_create(body: IncidentInput, ctx=Depends(identity), db: Session = Depends(get_db)):
    require(ctx, ('operator', 'manager'))
    owned(db, Asset, body.asset_id, ctx)
    row = raise_incident(db, ctx, body.asset_id, body.type, {'reason': body.reason})
    db.commit()
    return incident_out(db, row, True)


@router.get('/security/incidents/{incident_id}')
def incident_detail(incident_id: str, ctx=Depends(identity), db: Session = Depends(get_db)):
    require(ctx, ('viewer', 'operator', 'manager'))
    return incident_out(db, owned(db, Incident, incident_id, ctx), True)


class IncidentUpdate(Strict):
    state: Literal['acknowledged', 'closed']
    reason: str = Field(min_length=5, max_length=2000)


@router.patch('/security/incidents/{incident_id}')
def incident_update(incident_id: str, body: IncidentUpdate, ctx=Depends(identity), db: Session = Depends(get_db)):
    require(ctx, ('operator', 'manager'))
    row = owned(db, Incident, incident_id, ctx)
    db.query(Asset).filter_by(id=row.asset_id).with_for_update().one()
    db.refresh(row)
    if row.state == 'closed' or (row.state == 'open' and body.state == 'closed'):
        raise HTTPException(409, 'Reconoce el incidente antes de cerrarlo; un cierre es definitivo')
    row.state, row.responsible, row.updated_at = body.state, ctx['user_id'], now()
    audit(db, ctx, body.state, {'reason': body.reason}, row.asset_id, row.id)
    db.commit()
    return incident_out(db, row, True)


class CommandInput(Strict):
    incident_id: str
    intention_id: str = Field(min_length=8, max_length=100)
    type: Literal['inhibit_next_start', 'restore_start']
    reason: str = Field(min_length=5, max_length=2000)


def command_out(row):
    return {k: getattr(row, k) for k in ('id', 'incident_id', 'type', 'requester', 'reason', 'state', 'result', 'created_at')}


@router.post('/security/commands')
def command_request(body: CommandInput, ctx=Depends(identity), db: Session = Depends(get_db)):
    incident = owned(db, Incident, body.incident_id, ctx)
    if ctx['role'] != 'manager':
        audit(db, ctx, 'command_denied', {'reason': 'role'}, incident.asset_id, incident.id)
        db.commit()
        raise HTTPException(403, 'Permiso insuficiente')
    db.query(Asset).filter_by(id=incident.asset_id).with_for_update().one()
    row = db.query(Command).filter_by(tenant_id=ctx['tenant_id'], intention_id=body.intention_id).one_or_none()
    if row and (row.incident_id != body.incident_id or row.type != body.type or row.requester != ctx['user_id']):
        raise HTTPException(409, 'La intención ya existe con otros datos')
    if not row:
        row = Command(tenant_id=ctx['tenant_id'], requester=ctx['user_id'], **body.model_dump(), state='failed',
                      result='Instalación no homologada: no se despachó ninguna orden. Resultado físico no confirmado.')
        db.add(row)
        audit(db, ctx, 'command_denied', {'reason': 'hardware_not_approved', 'intention_id': body.intention_id}, incident.asset_id, incident.id)
        db.commit()
    return command_out(row)


@router.get('/security/commands/{command_id}')
def command_detail(command_id: str, ctx=Depends(identity), db: Session = Depends(get_db)):
    require(ctx, ('operator', 'manager'))
    return command_out(owned(db, Command, command_id, ctx))


@router.post('/security/commands/{command_id}/approve')
def command_approve(command_id: str, ctx=Depends(identity), db: Session = Depends(get_db)):
    row = owned(db, Command, command_id, ctx)
    audit(db, ctx, 'approval_denied', {'command_id': row.id, 'reason': 'control_not_homologated'}, incident_id=row.incident_id)
    db.commit()
    raise HTTPException(409, 'Control físico deshabilitado: falta homologación de la instalación y autenticación reforzada')


class PointInput(Strict):
    device_id: str
    source_id: str = Field(min_length=1, max_length=200)
    recorded_at: AwareDatetime
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    speed_kmh: float | None = Field(None, ge=0, le=300)
    quality: Literal['gps', 'network', 'unknown'] = 'unknown'
    acc: bool | None = None
    external_power: bool | None = None
    sos: bool | None = None


def detect(db, ctx, row, policy):
    if not policy or not policy.armed or utc(row.recorded_at) < utc(policy.updated_at) or (now()-utc(row.recorded_at)).total_seconds() > 300:
        return
    evidence = {'position_id': row.id, 'recorded_at': utc(row.recorded_at).isoformat(), 'received_at': utc(row.received_at).isoformat()}
    kinds = []
    if row.sos:
        kinds.append('sos')
    if row.external_power is False:
        kinds.append('external_power_lost')
    if utc(row.recorded_at).hour not in policy.allowed_hours_utc:
        if row.acc:
            kinds.append('acc_outside_schedule')
        if row.quality == 'gps' and (row.speed_kmh or 0) > 2:
            kinds.append('suspected_movement')
    if policy.zone and row.quality == 'gps':
        z = policy.zone
        distance = math.hypot((row.lat-z['lat'])*111320, (row.lon-z['lon'])*111320*math.cos(math.radians(z['lat'])))
        if distance > z['radius_m']:
            kinds.append('outside_zone')
    for kind in kinds:
        raise_incident(db, ctx, row.asset_id, kind, evidence)


@router.post('/ingest/positions')
def ingest(body: PointInput, ctx=Depends(identity), db: Session = Depends(get_db)):
    require(ctx, ('ingestor',))
    if utc(body.recorded_at) > now()+timedelta(minutes=5):
        raise HTTPException(422, 'Fecha del dispositivo futura')
    assignments = db.query(Assignment).filter_by(device_id=body.device_id, tenant_id=ctx['tenant_id']).filter(
        Assignment.valid_from <= body.recorded_at, or_(Assignment.valid_to.is_(None), Assignment.valid_to > body.recorded_at)).all()
    if len(assignments) != 1:
        raise HTTPException(403, 'Dispositivo sin asignación inequívoca para esta fecha y cliente')
    assignment = assignments[0]
    db.query(Device).filter_by(id=body.device_id).with_for_update().one()
    owned(db, Asset, assignment.asset_id, ctx)
    existing = db.query(Position).filter_by(device_id=body.device_id, source_id=body.source_id).first()
    if existing:
        if existing.tenant_id != ctx['tenant_id']:
            raise HTTPException(409, 'ID de origen ya procesado')
        return {'id': existing.id, 'duplicate': True}
    row = Position(tenant_id=ctx['tenant_id'], asset_id=assignment.asset_id, assignment_id=assignment.id,
                   received_at=now(), **body.model_dump())
    db.add(row)
    db.flush()
    detect(db, ctx, row, db.get(Policy, row.asset_id))
    db.commit()
    return {'id': row.id, 'duplicate': False}


def check_communications(db):
    """Run from systemd timer independently of Odoo and web sessions."""
    for policy in db.query(Policy).filter_by(armed=True):
        db.query(Tenant).filter_by(id=policy.tenant_id).with_for_update().one()
        db.refresh(policy)
        if not policy.armed:
            continue
        asset = db.get(Asset, policy.asset_id)
        state = asset_out(db, asset, now())
        if state['signal_state'] != 'received' and (now()-utc(policy.updated_at)).total_seconds() > 300:
            ctx = {'tenant_id': policy.tenant_id, 'user_id': 'system:signal-monitor'}
            raise_incident(db, ctx, asset.id, 'communication_failure', {'signal_state': state['signal_state']})
    db.commit()


@router.get('/sync/changes')
def sync_changes(cursor: str = '', limit: int = Query(100, ge=1, le=500), ctx=Depends(identity), db: Session = Depends(get_db)):
    require(ctx, ('manager',))
    query = db.query(Audit).filter_by(tenant_id=ctx['tenant_id'])
    if cursor:
        try:
            stamp, anchor_id = cursor.split('|', 1)
            stamp = datetime.fromisoformat(stamp)
            if stamp.tzinfo is None:
                raise ValueError()
        except ValueError:
            raise HTTPException(422, 'Cursor de sincronización inválido')
        query = query.filter(or_(Audit.created_at > stamp, (Audit.created_at == stamp) & (Audit.id > anchor_id)))
    rows = query.order_by(Audit.created_at, Audit.id).limit(limit + 1).all()
    page = rows[:limit]
    items = []
    for row in page:
        incident = db.get(Incident, row.incident_id) if row.incident_id else None
        asset = db.get(Asset, row.asset_id) if row.asset_id else None
        items.append({'event_id': row.id, 'incident': incident_out(db, incident) if incident else None,
                      'asset': {'asset_id': asset.id, 'name': asset.name, 'source_id': asset.source_id} if asset else None})
    return {'items': items, 'cursor': utc(page[-1].created_at).isoformat()+'|'+page[-1].id if page else cursor, 'has_more': len(rows) > limit}
