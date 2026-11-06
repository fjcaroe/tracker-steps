"""Persistent hourly rollups, dirty revision invalidation and bounded range edges."""
import json
from datetime import timedelta
from sqlalchemy import text
from .gps_metrics import summarize, stamp, VERSION, HALO_SECONDS

FIELDS = 'id,recorded_at,lat,lon,speed_kmh,quality,assignment_id'


def raw_window(db, tenant, asset, start, end):
    args = dict(tenant=tenant, asset=asset, lo=start-timedelta(seconds=HALO_SECONDS), hi=end+timedelta(seconds=HALO_SECONDS))
    # One predecessor also records long silence without scanning the intervening history.
    sql = f'''(SELECT {FIELDS} FROM gps_positions WHERE tenant_id=:tenant AND asset_id=:asset
               AND recorded_at>=:lo AND recorded_at<:hi)
              UNION ALL (SELECT {FIELDS} FROM gps_positions WHERE tenant_id=:tenant AND asset_id=:asset
               AND recorded_at<:lo ORDER BY recorded_at DESC,id DESC LIMIT 1)'''
    rows = db.execute(text(sql), args).mappings().fetchmany(100001)
    if len(rows) > 100000:
        raise ValueError('Demasiadas muestras por hora; requiere revisar la frecuencia GPS')
    return rows


def rebuild(db, limit=250):
    from sqlalchemy.orm import Session
    from sqlalchemy.engine import Connection
    # Pin the physical connection across per-bucket commits: a session advisory
    # lock must never be returned to a pooled connection while still held.
    if isinstance(db.get_bind(), Connection):
        return _rebuild(db,limit)
    with db.get_bind().connect() as connection, Session(bind=connection) as worker:
        return _rebuild(worker, limit)


def _rebuild(db, limit):
    # Session advisory lock avoids duplicate workers without holding an ingestion/tenant lock.
    if not db.execute(text('SELECT pg_try_advisory_lock(60110602)')).scalar(): return 0
    count = 0
    try:
        jobs = db.execute(text("SELECT * FROM gps_analytics_dirty WHERE bucket<=date_trunc('hour',now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC' ORDER BY bucket DESC,tenant_id,asset_id LIMIT :limit"), dict(limit=limit)).mappings().all()
        for job in jobs:
            start = stamp(job['bucket']); end = start+timedelta(hours=1)
            metric = summarize(raw_window(db,job['tenant_id'],job['asset_id'],start,end),start,end)
            db.execute(text('''INSERT INTO gps_analytics_hourly(tenant_id,asset_id,bucket,version,metrics)
                VALUES (:tenant,:asset,:bucket,:version,CAST(:metrics AS jsonb))
                ON CONFLICT(tenant_id,asset_id,bucket) DO UPDATE SET version=EXCLUDED.version,
                metrics=EXCLUDED.metrics,computed_at=now()'''), dict(tenant=job['tenant_id'],asset=job['asset_id'],bucket=start,version=VERSION,metrics=json.dumps(metric)))
            # A late insert racing this calculation leaves a newer revision queued.
            db.execute(text('DELETE FROM gps_analytics_dirty WHERE tenant_id=:tenant AND asset_id=:asset AND bucket=:bucket AND revision=:revision'),
                       dict(tenant=job['tenant_id'],asset=job['asset_id'],bucket=start,revision=job['revision']))
            db.commit(); count += 1
        return count
    finally:
        db.rollback()
        db.execute(text('SELECT pg_advisory_unlock(60110602)')); db.commit()
