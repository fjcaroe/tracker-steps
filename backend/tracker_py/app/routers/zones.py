"""Saved company zones and bounded, quality-aware position analysis."""
from datetime import timedelta
from types import SimpleNamespace
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, ConfigDict, AwareDatetime
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.fleet import Zone, Asset, Position, now
from app.routers.fleet import Strict, identity, owned, require, audit
from app.services.zone_metrics import polygon_info, summarize, MAX_GAP_SECONDS

router=APIRouter(prefix='/v1/zones',tags=['fleet-zones'])


class Vertex(Strict):
    lat:float=Field(ge=-80,le=80,allow_inf_nan=False)
    lon:float=Field(ge=-180,le=180,allow_inf_nan=False)


class ZoneInput(Strict):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    name:str=Field(min_length=1,max_length=150)
    purpose:Literal['operation','customer','base','restricted']='operation'
    color:str=Field('#6d963c',pattern=r'^#[0-9a-fA-F]{6}$')
    vertices:list[Vertex]=Field(min_length=3,max_length=100)
    active:bool=True


class ZoneUpdate(ZoneInput):
    version:int=Field(ge=1)


def output(row):
    return {**{k:getattr(row,k) for k in ('id','name','purpose','color','vertices','active','version','created_at','updated_at')},**polygon_info(row.vertices)}


def validate(body):
    try:polygon_info([p.model_dump() for p in body.vertices])
    except ValueError as exc:raise HTTPException(422,str(exc))


@router.get('')
def zones(ctx=Depends(identity),db:Session=Depends(get_db)):
    require(ctx,('viewer','operator','manager'))
    return [output(row) for row in db.query(Zone).filter_by(tenant_id=ctx['tenant_id']).order_by(Zone.name,Zone.id)]


@router.post('')
def create(body:ZoneInput,ctx=Depends(identity),db:Session=Depends(get_db)):
    require(ctx,('manager',))
    validate(body)
    row=Zone(tenant_id=ctx['tenant_id'],**body.model_dump())
    db.add(row);db.flush()
    audit(db,ctx,'zone_created',{'zone_id':row.id,'version':1,'name':row.name})
    db.commit()
    return output(row)


@router.patch('/{zone_id}')
def update(zone_id:str,body:ZoneUpdate,ctx=Depends(identity),db:Session=Depends(get_db)):
    require(ctx,('manager',))
    row=owned(db,Zone,zone_id,ctx)
    if body.version!=row.version:raise HTTPException(409,'La zona cambió. Actualiza antes de editarla.')
    validate(body)
    before=output(row)
    for key,value in body.model_dump(exclude={'version'}).items():setattr(row,key,value)
    row.version+=1;row.updated_at=now()
    audit(db,ctx,'zone_updated',{'zone_id':row.id,'before':before | {'created_at':before['created_at'].isoformat(),'updated_at':before['updated_at'].isoformat()},'version':row.version})
    db.commit()
    return output(row)


@router.get('/{zone_id}/report')
def report(zone_id:str,asset_id:str,start:AwareDatetime,end:AwareDatetime,ctx=Depends(identity),db:Session=Depends(get_db)):
    require(ctx,('viewer','operator','manager'))
    zone=owned(db,Zone,zone_id,ctx)
    asset=owned(db,Asset,asset_id,ctx)
    if end<=start or end-start>timedelta(days=31):
        raise HTTPException(422,'Selecciona un período mayor a cero y de hasta 31 días.')
    if end>now()+timedelta(minutes=5):
        raise HTTPException(422,'El período no puede terminar en el futuro.')
    padding=timedelta(seconds=MAX_GAP_SECONDS)
    points=db.query(Position).filter(Position.tenant_id==ctx['tenant_id'],Position.asset_id==asset.id,
          Position.recorded_at>=start-padding,Position.recorded_at<=end+padding).order_by(Position.recorded_at,Position.id).limit(20001).all()
    if len(points)>20000:raise HTTPException(422,'Hay más de 20.000 posiciones. Reduce el período para obtener un reporte completo.')
    # Ambiguous equal-time fixes must not manufacture movement or overlapping time.
    unique=[]
    for p in points:
        if unique and unique[-1].recorded_at==p.recorded_at:
            last=unique[-1]
            if (last.lat,last.lon,last.assignment_id,last.quality,last.speed_kmh)!=(p.lat,p.lon,p.assignment_id,p.quality,p.speed_kmh):
                unique[-1]=SimpleNamespace(recorded_at=p.recorded_at,lat=p.lat,lon=p.lon,
                    assignment_id=p.assignment_id,quality='ambiguous',speed_kmh=None)
        else:unique.append(p)
    return {'zone':output(zone),'asset':{'id':asset.id,'name':asset.name,'plate':asset.plate},
            'start':start,'end':end,'generated_at':now(),**summarize(zone.vertices,unique,start,end)}
