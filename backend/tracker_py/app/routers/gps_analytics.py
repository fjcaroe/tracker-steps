from datetime import timedelta
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AwareDatetime
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.fleet import Asset, now
from app.routers.fleet import identity, require, scoped
from app.services.gps_analytics import raw_window
from app.services.gps_metrics import summarize, stamp, VERSION

router = APIRouter(prefix='/v1/assets', tags=['gps-analytics'])
CHILE = ZoneInfo('America/Santiago')


def combine(parts):
    result = {key: sum(p.get(key,0) for p in parts) for key in ('point_count','distance_m','moving_seconds','stop_count','gap_count')}
    result['max_speed'] = max((p['max_speed'] for p in parts if p.get('max_speed') is not None), default=None)
    result['first_at'] = min((p['first_at'] for p in parts if p.get('first_at')),default=None)
    result['last_at'] = max((p['last_at'] for p in parts if p.get('last_at')),default=None)
    return result


@router.get('/analytics')
def analytics(asset_ids: str = Query(...,max_length=3300), since: AwareDatetime = Query(...), until: AwareDatetime = Query(...),
              ctx=Depends(identity), db: Session=Depends(get_db)):
    require(ctx, ('viewer','operator','manager'))
    ids = sorted(set(asset_ids.split(',')))
    if not 1 <= len(ids) <= 50 or any(not 1 <= len(i) <= 64 for i in ids):
        raise HTTPException(422,'Seleccione hasta 50 vehículos por consulta')
    since,until = stamp(since),stamp(until)
    if not since < until or until-since > timedelta(days=31) or until > now()+timedelta(minutes=5):
        raise HTTPException(422,'Período inválido: máximo 31 días')
    allowed = scoped(db.query(Asset).filter(Asset.tenant_id==ctx['tenant_id'],Asset.id.in_(ids)),Asset.id,ctx).all()
    if {a.id for a in allowed} != set(ids): raise HTTPException(404,'Vehículo no disponible')
    lo = since.replace(minute=0,second=0,microsecond=0)
    hi = until.replace(minute=0,second=0,microsecond=0)
    # One MVCC snapshot for both cache and invalidation state. Missing empty
    # hours are zero, but missing/dirty hours containing fixes remain pending.
    full_lo = lo+timedelta(hours=1) if since!=lo else lo
    records = db.execute(text('''WITH slices AS (
        SELECT COALESCE(h.asset_id,d.asset_id) asset_id, COALESCE(h.bucket,d.bucket) bucket,
               h.metrics,h.version,h.computed_at,d.revision
        FROM (SELECT * FROM gps_analytics_hourly WHERE tenant_id=:tenant AND asset_id=ANY(:ids)
              AND bucket>=:lo AND bucket<:hi) h
        FULL OUTER JOIN (SELECT * FROM gps_analytics_dirty WHERE tenant_id=:tenant AND asset_id=ANY(:ids)
              AND bucket>=:lo AND bucket<:hi) d USING(tenant_id,asset_id,bucket))
        SELECT asset_id,(bucket AT TIME ZONE 'America/Santiago')::date day,
          count(*) FILTER(WHERE revision IS NOT NULL OR version IS DISTINCT FROM 2) pending_hours,
          min(computed_at) FILTER(WHERE revision IS NULL AND version=2) computed_at,
          jsonb_build_object('point_count',COALESCE(sum((metrics->>'point_count')::double precision) FILTER(WHERE version=2 AND revision IS NULL),0),'distance_m',COALESCE(sum((metrics->>'distance_m')::double precision) FILTER(WHERE version=2 AND revision IS NULL),0),'moving_seconds',COALESCE(sum((metrics->>'moving_seconds')::double precision) FILTER(WHERE version=2 AND revision IS NULL),0),'stop_count',COALESCE(sum((metrics->>'stop_count')::double precision) FILTER(WHERE version=2 AND revision IS NULL),0),'gap_count',COALESCE(sum((metrics->>'gap_count')::double precision) FILTER(WHERE version=2 AND revision IS NULL),0),'max_speed',max((metrics->>'max_speed')::double precision) FILTER(WHERE version=2 AND revision IS NULL),'first_at',min(metrics->>'first_at') FILTER(WHERE version=2 AND revision IS NULL),'last_at',max(metrics->>'last_at') FILTER(WHERE version=2 AND revision IS NULL)) metrics
        FROM slices GROUP BY asset_id,day
        '''),dict(tenant=ctx['tenant_id'],ids=ids,lo=full_lo,hi=hi)).mappings().all()
    grouped={i:[] for i in ids};pending={i:0 for i in ids};computed=[]
    for row in records:
        pending[row['asset_id']]+=row['pending_hours']
        grouped[row['asset_id']].append((str(row['day']),row['metrics']))
        if row['computed_at']:computed.append(stamp(row['computed_at']))
    for asset in ids:
        edges=[]
        if since<min(full_lo,until): edges.append((since,min(full_lo,until)))
        if hi>=full_lo and hi<until: edges.append((hi,until))
        for start,end in edges:
            try: metric=summarize(raw_window(db,ctx['tenant_id'],asset,start,end),start,end)
            except ValueError as error: raise HTTPException(422,str(error))
            grouped[asset].append((start.astimezone(CHILE).date().isoformat(),metric))
    items=[]
    for asset in ids:
        daily={}
        for bucket,metric in grouped[asset]:
            if metric['point_count']:
                daily.setdefault(bucket,[]).append(metric)
        parts=[m for _,m in grouped[asset]]
        items.append(dict(asset_id=asset,metrics=combine(parts),complete=pending[asset]==0,pending_hours=pending[asset],
                          daily=[dict(day=day,**combine(metrics)) for day,metrics in sorted(daily.items())]))
    return dict(items=items,since=since,until=until,timezone='America/Santiago',metrics_version=VERSION,
                computed_at=min(computed) if computed else now(),generated_at=now())
