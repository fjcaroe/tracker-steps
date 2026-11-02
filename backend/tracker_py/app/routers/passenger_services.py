"""I9: admin schedules manifests; drivers can only read their own assignments."""
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.security import get_current_user, assert_cost_center_access
from app.db.session import get_db
from app.models.users import User
from app.models.machines import Machine
from app.models.cost_centers import CostCenter
from app.models.mobile import MobileRoute
from app.models.passenger_services import PassengerService, ServiceStop, ServicePassenger, PassengerEvent

router = APIRouter(prefix='/mobile/services', tags=['passenger-services'])


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class StopIn(Strict):
    id: uuid.UUID
    name: str = Field(min_length=1, max_length=150)
    scheduled_at: AwareDatetime
    lat: float | None = Field(None, ge=-90, le=90, allow_inf_nan=False)
    lon: float | None = Field(None, ge=-180, le=180, allow_inf_nan=False)

    @model_validator(mode='after')
    def coordinates(self):
        if (self.lat is None) != (self.lon is None):
            raise ValueError('Latitud y longitud deben indicarse juntas.')
        return self


def document_key(value):
    # RUT/ID comparisons ignore display punctuation, preserving the displayed ID.
    return ''.join(ch for ch in value.upper() if ch.isalnum())


class PassengerIn(Strict):
    id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    document: str = Field(min_length=1, max_length=40)
    boarding_stop_id: uuid.UUID
    alighting_stop_id: uuid.UUID
    seat: int | None = Field(None, ge=1, le=250, strict=True)


class ServiceIn(Strict):
    id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    route_id: uuid.UUID
    driver_user_id: int = Field(ge=1, strict=True)
    stops: list[StopIn] = Field(min_length=2, max_length=100)
    passengers: list[PassengerIn] = Field(min_length=1, max_length=1000)

    @model_validator(mode='after')
    def itinerary(self):
        stop_ids=[s.id for s in self.stops]
        if len(set(stop_ids)) != len(stop_ids):
            raise ValueError('Las paradas deben tener identificadores distintos.')
        if any(a.scheduled_at >= b.scheduled_at for a,b in zip(self.stops,self.stops[1:])):
            raise ValueError('Los horarios de paradas deben estar en orden creciente.')
        documents=[document_key(p.document) for p in self.passengers]
        if not all(documents) or len(set(documents)) != len(documents):
            raise ValueError('Cada pasajero debe tener un RUT/ID distinto y válido.')
        if len({p.id for p in self.passengers}) != len(self.passengers):
            raise ValueError('Los pasajeros deben tener identificadores distintos.')
        positions={value:i for i,value in enumerate(stop_ids)}
        for passenger in self.passengers:
            if passenger.boarding_stop_id not in positions or passenger.alighting_stop_id not in positions:
                raise ValueError('Las paradas del pasajero deben pertenecer al servicio.')
            if positions[passenger.boarding_stop_id] >= positions[passenger.alighting_stop_id]:
                raise ValueError('La bajada debe ser posterior a la subida.')
        return self


def check_capacity(payload, capacity):
    positions={s.id:i for i,s in enumerate(payload.stops)}
    for segment in range(len(payload.stops)-1):
        aboard=[p for p in payload.passengers if positions[p.boarding_stop_id] <= segment < positions[p.alighting_stop_id]]
        if len(aboard)>capacity:
            raise HTTPException(422,'La nómina supera la capacidad del vehículo en un tramo.')
        seats=[p.seat for p in aboard if p.seat is not None]
        if any(s>capacity for s in seats) or len(set(seats))!=len(seats):
            raise HTTPException(422,'Asiento fuera de capacidad o repetido en el mismo tramo.')


def service_out(db, row):
    route=db.get(MobileRoute,row.route_id)
    machine=db.get(Machine,route.machine_id)
    driver=db.get(User,row.driver_user_id)
    stops=db.query(ServiceStop).filter_by(service_id=row.id).order_by(ServiceStop.position).all()
    passengers=db.query(ServicePassenger).filter_by(service_id=row.id).order_by(ServicePassenger.name,ServicePassenger.id).all()
    result = {
        'id':str(row.id),'name':row.name,'route_id':str(row.route_id),'route_name':route.name,'route_status':route.status,
        'machine_id':machine.id,'machine_name':machine.name,'plate':machine.plate,
        'driver_user_id':driver.id,'driver_name':driver.full_name,'capacity':row.capacity,
        'stops':[{'id':str(s.id),'name':s.name,'scheduled_at':s.scheduled_at,'lat':s.lat,'lon':s.lon} for s in stops],
        'passengers':[{'id':str(p.id),'name':p.name,'document':p.document,'boarding_stop_id':str(p.boarding_stop_id),
                       'alighting_stop_id':str(p.alighting_stop_id),'seat':p.seat} for p in passengers],
        'sync':{'schema_version':1,'source':'tracker','service_id':str(row.id),
                'machine_external_id':machine.external_id,'cost_center_id':machine.cost_center_id,
                'cost_center_external_id':db.get(CostCenter,machine.cost_center_id).external_id if machine.cost_center_id else None},
    }
    result['sync']['content_hash']=hashlib.sha256(json.dumps(result,sort_keys=True,default=str).encode()).hexdigest()
    return result


def authorized_service(db, current, service_id):
    row=db.get(PassengerService,service_id)
    if row is None or (not current.is_admin and row.driver_user_id != current.id):
        raise HTTPException(404,'Servicio no encontrado.')
    machine=db.get(Machine,db.get(MobileRoute,row.route_id).machine_id)
    assert_cost_center_access(db,current,machine.cost_center_id)
    return row


@router.post('')
def create_service(payload: ServiceIn, response: Response, db: Session=Depends(get_db), current: User=Depends(get_current_user)):
    response.headers['Cache-Control']='no-store'
    if not current.is_admin:
        raise HTTPException(403,'Solo un administrador puede programar servicios.')
    payload_hash=hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
    existing=db.get(PassengerService,payload.id)
    if existing:
        if existing.payload_hash!=payload_hash:
            raise HTTPException(409,'El identificador ya corresponde a otro contenido.')
        return service_out(db,existing)
    route=db.query(MobileRoute).filter_by(id=payload.route_id).with_for_update().one_or_none()
    if route is None or route.status=='cancelled':
        raise HTTPException(422,'Seleccione una ruta existente que no esté cancelada.')
    machine=db.query(Machine).filter_by(id=route.machine_id).with_for_update().one_or_none()
    if machine is None or not machine.is_active or not machine.passenger_capacity:
        raise HTTPException(422,'Configure la capacidad real de pasajeros en el vehículo activo antes de programar.')
    driver=db.get(User,payload.driver_user_id)
    if driver is None or not driver.is_active:
        raise HTTPException(422,'Seleccione un usuario conductor activo.')
    assert_cost_center_access(db,driver,machine.cost_center_id)
    check_capacity(payload,machine.passenger_capacity)
    row=PassengerService(id=payload.id,name=payload.name,route_id=route.id,driver_user_id=driver.id,
                         capacity=machine.passenger_capacity,payload_hash=payload_hash,created_by=current.id)
    try:
        db.add(row);db.flush()
        db.add_all([ServiceStop(id=s.id,service_id=row.id,position=i,name=s.name,
                               scheduled_at=s.scheduled_at.astimezone(timezone.utc),lat=s.lat,lon=s.lon) for i,s in enumerate(payload.stops)])
        db.flush()
        db.add_all([ServicePassenger(service_id=row.id,document_key=document_key(p.document),**p.model_dump()) for p in payload.passengers])
        db.commit()
    except IntegrityError:
        db.rollback()
        existing=db.get(PassengerService,payload.id)
        if existing and existing.payload_hash==payload_hash:
            return service_out(db,existing)
        raise HTTPException(409,'Identificadores de servicio, parada o pasajero ya utilizados.')
    return service_out(db,row)


@router.get('')
def list_services(response: Response, mine: bool=True, limit: int=Query(50,ge=1,le=200),
                  db: Session=Depends(get_db),current: User=Depends(get_current_user)):
    response.headers['Cache-Control']='no-store'
    query=db.query(PassengerService)
    if mine or not current.is_admin:
        query=query.filter(PassengerService.driver_user_id==current.id)
    rows=query.order_by(PassengerService.created_at.desc(),PassengerService.id).limit(limit).all()
    result=[]
    for row in rows:
        try:
            authorized_service(db,current,row.id)
        except HTTPException as exc:
            if exc.status_code==403:
                continue
            raise
        result.append(service_out(db,row))
    return result


@router.get('/{service_id}')
def get_service(service_id: uuid.UUID,response: Response,db: Session=Depends(get_db),current: User=Depends(get_current_user)):
    response.headers['Cache-Control']='no-store'
    return service_out(db,authorized_service(db,current,service_id))


class EventIn(Strict):
    id: uuid.UUID
    passenger_id: uuid.UUID
    kind: Literal['boarded', 'alighted', 'no_show']
    expected_version: int = Field(ge=0, strict=True)
    occurred_at: AwareDatetime
    lat: float | None = Field(None, ge=-90, le=90, allow_inf_nan=False)
    lon: float | None = Field(None, ge=-180, le=180, allow_inf_nan=False)
    accuracy_m: float | None = Field(None, ge=0, allow_inf_nan=False)

    @model_validator(mode='after')
    def location(self):
        if (self.lat is None) != (self.lon is None) or (self.lat is None and self.accuracy_m is not None):
            raise ValueError('Indique coordenadas juntas o registre sin ubicación.')
        return self


def event_rows(db, service_id):
    return db.query(PassengerEvent).filter_by(service_id=service_id).order_by(PassengerEvent.sequence).all()


def passenger_states(events):
    return {str(e.passenger_id): e.kind for e in events}


def manifest_out(db, row):
    result = service_out(db, row)
    events = event_rows(db, row.id)
    states = passenger_states(events)
    result['manifest_version'] = len(events)
    result['occupied'] = sum(state == 'boarded' for state in states.values())
    for passenger in result['passengers']:
        passenger['state'] = states.get(passenger['id'], 'pending')
    result['events'] = [dict(id=str(e.id), passenger_id=str(e.passenger_id), kind=e.kind,
                             sequence=e.sequence, occurred_at=e.occurred_at, received_at=e.received_at,
                             lat=e.lat, lon=e.lon, accuracy_m=e.accuracy_m, actor_id=e.actor_id) for e in events]
    result['sync']['schema_version'] = 2
    result['sync'].pop('content_hash')
    result['sync']['content_hash'] = hashlib.sha256(json.dumps(result, sort_keys=True, default=str).encode()).hexdigest()
    return result


@router.get('/{service_id}/manifest')
def get_manifest(service_id: uuid.UUID, response: Response, db: Session=Depends(get_db), current: User=Depends(get_current_user)):
    response.headers['Cache-Control'] = 'no-store'
    return manifest_out(db, authorized_service(db, current, service_id))


@router.post('/{service_id}/events')
def record_event(service_id: uuid.UUID, payload: EventIn, response: Response,
                 db: Session=Depends(get_db), current: User=Depends(get_current_user)):
    response.headers['Cache-Control'] = 'no-store'
    row = authorized_service(db, current, service_id)
    # Serialize all writers of a manifest, including two phones belonging to the driver.
    db.query(PassengerService).filter_by(id=row.id).with_for_update().one()
    db.refresh(row)
    authorized_service(db, current, service_id)
    payload_hash = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()
    existing = db.get(PassengerEvent, payload.id)
    if existing:
        if existing.service_id != row.id or existing.actor_id != current.id or existing.payload_hash != payload_hash:
            raise HTTPException(409, 'El código del evento ya corresponde a otro registro. No se ha aplicado.')
        return manifest_out(db, row)
    if db.get(MobileRoute, row.route_id).status == 'cancelled':
        raise HTTPException(409, 'La ruta fue cancelada. Conserva los pendientes y consulta al supervisor.')
    now = datetime.now(timezone.utc)
    if payload.occurred_at > now + timedelta(minutes=5) or payload.occurred_at < now - timedelta(days=7):
        raise HTTPException(422, 'La hora debe estar dentro de los últimos siete días y no en el futuro.')
    passengers = db.query(ServicePassenger).filter_by(service_id=row.id).all()
    passenger = next((p for p in passengers if p.id == payload.passenger_id), None)
    if passenger is None:
        raise HTTPException(422, 'El pasajero no pertenece a este servicio.')
    events = event_rows(db, row.id)
    if payload.expected_version != len(events):
        raise HTTPException(409, 'El manifiesto cambió en otro dispositivo. Actualiza y revisa los pendientes antes de continuar.')
    states = passenger_states(events)
    state = states.get(str(passenger.id), 'pending')
    allowed = {'pending': {'boarded', 'no_show'}, 'no_show': {'boarded'}, 'boarded': {'alighted'}, 'alighted': set()}
    if payload.kind not in allowed[state]:
        raise HTTPException(409, 'El estado del pasajero cambió. Actualiza y revisa el registro.')
    if payload.kind == 'boarded':
        aboard = [p for p in passengers if states.get(str(p.id)) == 'boarded']
        if len(aboard) >= row.capacity:
            raise HTTPException(409, 'Capacidad completa. Registra los descensos antes de una nueva subida.')
        if passenger.seat is not None and any(p.seat == passenger.seat for p in aboard):
            raise HTTPException(409, 'El asiento aún está ocupado. Registra primero el descenso correspondiente.')
    db.add(PassengerEvent(id=payload.id, service_id=row.id, passenger_id=passenger.id, sequence=len(events)+1,
                         kind=payload.kind, occurred_at=payload.occurred_at, lat=payload.lat, lon=payload.lon,
                         accuracy_m=payload.accuracy_m, actor_id=current.id, payload_hash=payload_hash))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'El manifiesto recibió otro registro. Actualiza y revisa antes de reintentar.')
    return manifest_out(db, row)
