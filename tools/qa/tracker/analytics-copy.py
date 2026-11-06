"""Postgres-only rehearsal on a fresh private copy; rollback all fixture business rows."""
import json,os,sys,time
from pathlib import Path
from datetime import datetime,timedelta,timezone
from sqlalchemy import create_engine,text,event
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from app.db.session import get_db
from app.main import app
from app.routers.fleet import identity
from app.services.gps_analytics import rebuild
from app.services.gps_metrics import summarize

engine=create_engine(os.environ['DATABASE_URL'])
assert engine.url.database.startswith('TRACKER_ANALYTICS_QA_')
with engine.connect() as connection:
    # A connection-bound Session retains the worker advisory lock across commits.
    db=Session(bind=connection)
    while rebuild(db,5000):pass
    original=db.execute(text('SELECT count(*) FROM gps_positions')).scalar()
    tenant=db.execute(text('SELECT id FROM gps_tenants ORDER BY id LIMIT 1')).scalar()
    asset=db.execute(text('SELECT id FROM gps_assets WHERE tenant_id=:t LIMIT 1'),{'t':tenant}).scalar()
    assert asset
    ctx={'tenant_id':tenant,'user_id':'private-qa','role':'viewer','asset_ids':[asset]}
    app.dependency_overrides[identity]=lambda:ctx
    def session():yield db
    app.dependency_overrides[get_db]=session
    client=TestClient(app)
    end=datetime.now(timezone.utc).replace(minute=0,second=0,microsecond=0)
    start=end-timedelta(days=30)
    url='/v1/assets/analytics'
    params={'asset_ids':asset,'since':start.isoformat(),'until':end.isoformat()}
    before=time.perf_counter();response=client.get(url,params=params);elapsed=time.perf_counter()-before
    assert response.status_code==200,response.text
    data=response.json();assert data['items'][0]['complete']
    raw=db.execute(text('SELECT * FROM gps_positions WHERE tenant_id=:t AND asset_id=:a AND recorded_at>=:lo AND recorded_at<:hi'),dict(t=tenant,a=asset,lo=start-timedelta(minutes=20),hi=end+timedelta(minutes=20))).mappings().all()
    expected=summarize(raw,start,end);actual=data['items'][0]['metrics']
    for field in ('point_count','distance_m','moving_seconds','stop_count'):
        assert abs(actual[field]-expected[field])<.001,(field,actual,expected)
    # Scope narrowing, cross-tenant requests, invalid intervals and batch bounds.
    ctx['asset_ids']=[];assert client.get(url,params=params).status_code==404
    ctx['asset_ids']=[asset]
    assert client.get(url,params={**params,'until':start.isoformat()}).status_code==422
    assert client.get(url,params={**params,'asset_ids':','.join(str(i) for i in range(51))}).status_code==422
    # Rollup + dirty flag use one statement/snapshot; an invalidated hour must
    # never be served as a complete zero while a worker is pending.
    db.execute(text('INSERT INTO gps_analytics_dirty(tenant_id,asset_id,bucket) VALUES (:t,:a,:b) ON CONFLICT DO NOTHING'),dict(t=tenant,a=asset,b=start))
    assert not client.get(url,params=params).json()['items'][0]['complete']
    db.rollback()
    assert db.execute(text('SELECT count(*) FROM gps_positions')).scalar()==original
    print('GPS_ANALYTICS_COPY_OK '+json.dumps({'real_samples':len(raw),'warm_30_days_seconds':elapsed,'response_bytes':len(response.content),'version':data['metrics_version']}))
    db.close()
