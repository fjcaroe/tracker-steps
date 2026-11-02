import asyncio,json,os,socket,time,uuid
from datetime import datetime,timezone
from .server import Receiver
from .store import Store
from .starter import Control,encode

IMEI='000000000000001'
class Writer:
    def __init__(self):self.frames=[]
    def is_closing(self):return False
    def write(self,value):self.frames.append(value)
    async def drain(self):pass

def receiver(tmp_path):
    p=tmp_path/'map.json';p.write_text(json.dumps({IMEI:dict(issuer='CERRO_EL_PLOMO',company_id=2,device_id='00000000-0000-0000-0000-000000000001',mode='forward')}))
    r=Receiver(Store(tmp_path/'inbox.sqlite'),p);r.connections[IMEI]=Writer();r.points[IMEI]=(dict(recorded_at=datetime.now(timezone.utc).isoformat(),quality='gps',acc=False,speed_kmh=0),time.time());return r

def message(action='inhibit_next_start'):
    return dict(operation='dispatch',command_id=str(uuid.uuid4()),imei=IMEI,issuer='CERRO_EL_PLOMO',company_id=2,device_id='00000000-0000-0000-0000-000000000001',action=action,deadline=time.time()+8)

def test_wire_and_no_repeat_after_restart(tmp_path):
    r=receiver(tmp_path);control=Control(r,os.getuid());job=message()
    assert asyncio.run(control.execute(job))['state']=='sent_unconfirmed'
    assert r.connections[IMEI].frames==[('**,imei:'+IMEI+',J').encode()]
    assert asyncio.run(control.execute(job))['state']=='uncertain'
    r.store=Store(tmp_path/'inbox.sqlite');assert asyncio.run(control.execute(job))['state']=='uncertain'
    assert len(r.connections[IMEI].frames)==1
    assert asyncio.run(control.execute(message('restore_start')))['state']=='sent_unconfirmed'
    assert r.connections[IMEI].frames[-1]==('**,imei:'+IMEI+',K').encode()

def test_no_queue_on_expiry_disconnect_or_motion(tmp_path):
    r=receiver(tmp_path);control=Control(r,os.getuid())
    assert asyncio.run(control.execute({**message(),'deadline':time.time()-1}))['state']=='failed'
    assert asyncio.run(control.execute({**message(),'company_id':99}))['state']=='failed'
    r.points[IMEI][0]['acc']=True
    assert asyncio.run(control.execute(message()))['state']=='failed'
    r.points[IMEI][0]['acc']=False;r.points[IMEI][0]['speed_kmh']=10
    assert asyncio.run(control.execute(message()))['state']=='failed'
    r.points[IMEI][0]['speed_kmh']=0;r.points[IMEI]=(r.points[IMEI][0],time.time()-120)
    assert asyncio.run(control.execute(message()))['state']=='failed'
    assert r.connections[IMEI].frames==[]
    r.connections.clear();assert asyncio.run(control.execute(message('restore_start')))['state']=='failed'

def test_private_socket_rejects_other_uid(tmp_path):
    async def scenario():
        r=receiver(tmp_path);path=str(tmp_path/'private.sock');server=await asyncio.start_unix_server(Control(r,os.getuid()+1).connection,path)
        async with server:
            reader,writer=await asyncio.open_unix_connection(path);writer.write(json.dumps(message()).encode()+b'\n');await writer.drain();value=json.loads(await reader.readline());writer.close();await writer.wait_closed();assert value['state']=='failed';assert r.connections[IMEI].frames==[]
    asyncio.run(scenario())

def test_live_tcp_connection_receives_exact_command(tmp_path):
    async def scenario():
        r=receiver(tmp_path);r.connections.clear();r.points.clear()
        tcp=await asyncio.start_server(r.connection,'127.0.0.1',0)
        path=str(tmp_path/'private-allowed.sock');private=await asyncio.start_unix_server(Control(r,os.getuid()).connection,path)
        async with tcp,private:
            gps,writer=await asyncio.open_connection('127.0.0.1',tcp.sockets[0].getsockname()[1]);writer.write(('##,imei:'+IMEI+',A').encode());await writer.drain();assert await gps.readexactly(4)==b'LOAD'
            stamp=datetime.now(timezone.utc);frame=('imei:'+IMEI+',tracker,'+stamp.strftime('%y%m%d%H%M%S')+',,F,'+stamp.strftime('%H%M%S')+'.000,A,3300.0000,S,07000.0000,W,0.00,0,,0,0,;').encode()
            writer.write(frame);await writer.drain()
            for _ in range(50):
                if IMEI in r.points:break
                await asyncio.sleep(.01)
            reader,control=await asyncio.open_unix_connection(path);control.write(json.dumps(message()).encode()+b'\n');await control.drain();result=json.loads(await reader.readline());assert result['state']=='sent_unconfirmed'
            assert await asyncio.wait_for(gps.readexactly(len(encode(IMEI,'inhibit_next_start'))),1)==encode(IMEI,'inhibit_next_start')
            control.close();writer.close();await control.wait_closed();await writer.wait_closed()
    asyncio.run(scenario())
