"""End-to-end QA with the deployed API and a fresh COPY of Tracker production.

Run using the API venv as postgres, PYTHONPATH=release:deployed-backend.
Fixtures and synthetic identifiers are confined to COBAN_QA_* databases.
"""
import asyncio
from datetime import datetime,timezone,timedelta
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from urllib.request import Request,urlopen
from urllib.error import HTTPError


def main():
    assert os.environ['DATABASE_URL'].rsplit('/',1)[-1].startswith('COBAN_QA_')
    os.environ['JWT_SECRET']='test-only-coban-rehearsal'
    os.environ['TRACKER_BRIDGE_KEYS']=json.dumps({'CERRO_EL_PLOMO':'test-only-coban-bridge'})
    from app.main import app
    from app.db.session import SessionLocal,engine
    from app.models.fleet import Tenant,Asset,Device,DeviceRegistration,Assignment,Position
    from .store import Store
    from .server import Receiver,flush,token
    with SessionLocal() as db:
        assert db.execute(__import__('sqlalchemy').text('SELECT current_database()')).scalar().startswith('COBAN_QA_')
        tenant=db.query(Tenant).filter_by(issuer='CERRO_EL_PLOMO',company_id=2).one()
        foreign=db.query(Tenant).filter_by(issuer='CERRO_EL_PLOMO',company_id=3).one()
        tenant_id=tenant.id
        asset=Asset(tenant_id=tenant.id,source_id='private-coban:'+str(uuid.uuid4()),name='Private Coban QA vehicle')
        device=Device(imei='000000000000001',brand='QA-only',model='synthetic gps103',protocol='gps103')
        db.add_all([asset,device]);db.flush()
        db.add(DeviceRegistration(tenant_id=tenant.id,device_id=device.id))
        assignment=Assignment(tenant_id=tenant.id,device_id=device.id,asset_id=asset.id,valid_from=datetime.now(timezone.utc)-timedelta(days=1))
        db.add(assignment);db.commit();device_id=device.id;asset_id=asset.id
    with tempfile.TemporaryDirectory(prefix='coban-private-qa-') as tmp:
        root=Path(tmp);key=root/'key.json';mapping=root/'devices.json'
        key.write_text(json.dumps({'issuer':'CERRO_EL_PLOMO','key':'test-only-coban-bridge'}))
        mapping.write_text(json.dumps({'000000000000001':{'issuer':'CERRO_EL_PLOMO','company_id':2,'device_id':device_id,'mode':'forward'}}))
        store=Store(root/'queue.sqlite');receiver=Receiver(store,mapping)
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));api_port=sock.getsockname()[1]
        cfg={'api':'http://127.0.0.1:'+str(api_port),'mapping':str(mapping),'key_file':str(key)}
        api=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(api_port),'--log-level','error'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(60):
                try:
                    with urlopen(cfg['api']+'/health',timeout=1) as response:
                        if response.status==200:break
                except OSError:time.sleep(.25)
            else:raise RuntimeError('Private QA API did not start')
            now=datetime.now(timezone.utc)
            frame=('imei:000000000000001,tracker,'+now.strftime('%y%m%d%H%M%S')+',,F,'+now.strftime('%H%M%S')+'.000,A,3300.0000,S,07000.0000,W,10.00,0,,1,0,;').encode()
            async def tcp_flow():
                listener=await asyncio.start_server(receiver.connection,'127.0.0.1',0)
                reader,writer=await asyncio.open_connection('127.0.0.1',listener.sockets[0].getsockname()[1])
                try:
                    writer.write(b'##,imei:000000000000001,A');await writer.drain()
                    assert await asyncio.wait_for(reader.readexactly(4),2)==b'LOAD'
                    writer.write(frame[:40]);await writer.drain();writer.write(frame[40:]+frame);await writer.drain()
                    for _ in range(50):
                        if store.status()['queued']==1:break
                        await asyncio.sleep(.02)
                    assert store.status()['queued']==1
                finally:
                    writer.close();await writer.wait_closed();listener.close();await listener.wait_closed()
            asyncio.run(tcp_flow())
            # Re-open the outbox to prove that TCP reception survived a restart.
            store=Store(root/'queue.sqlite');flush(store,cfg);assert store.status()['queued']==0
            with SessionLocal() as db:
                rows=db.query(Position).filter_by(device_id=device_id).all();assert len(rows)==1
                point=rows[0];assert point.tenant_id==tenant_id and point.asset_id==asset_id
                assert point.lat==-33 and point.lon==-70 and abs(point.speed_kmh-18.52)<.001 and point.acc is True
            # Consult the REAL fleet projection, not merely the ingestion result.
            from jose import jwt
            stamp=int(time.time())
            view_token=jwt.encode({'iss':'CERRO_EL_PLOMO','aud':'steps-tracker-v1','sub':'qa:viewer','company_id':2,'role':'viewer','iat':stamp,'exp':stamp+60},'test-only-coban-bridge',algorithm='HS256')
            headers={'Authorization':'Bearer '+view_token}
            with urlopen(Request(cfg['api']+'/v1/assets/'+asset_id,headers=headers),timeout=5) as response:
                assert json.load(response)['last_position']['lat']==-33
            payload=json.loads(store.pending()[0][3]) if store.pending() else {'device_id':device_id,'source_id':'private-cross-tenant','recorded_at':now.isoformat(),'lat':-33,'lon':-70,'quality':'gps'}
            headers={'Authorization':'Bearer '+token('CERRO_EL_PLOMO',3,'test-only-coban-bridge'),'Content-Type':'application/json'}
            try:urlopen(Request(cfg['api']+'/v1/ingest/positions',headers=headers,data=json.dumps(payload).encode()),timeout=5)
            except HTTPError as exc:assert exc.code==403
            else:raise AssertionError('Cross-company ingestion allowed')
            print('COBAN_COPY_QA_OK tcp=True durable_restart=True duplicate_suppressed=True fleet_visible=True company_isolation=True')
        finally:
            api.terminate();api.wait(timeout=15)


if __name__=='__main__':main()
