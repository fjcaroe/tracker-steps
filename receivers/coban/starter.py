"""Private Unix socket, authorized peer UID, live connection and at-most-once J/K.

Wire reference: Traccar Gps103ProtocolEncoder (Apache-2.0), J/K commands.
https://github.com/traccar/traccar/blob/master/src/main/java/org/traccar/protocol/Gps103ProtocolEncoder.java
No arbitrary payloads, persistent actuator queue or quickstop are supported.
"""
import asyncio, json, math, os, re, socket, struct, time
from datetime import datetime, timezone
from .server import mapping


def encode(imei, action):
    if not re.fullmatch(r'\d{15}',imei) or action not in ('inhibit_next_start','restore_start'):
        raise ValueError('unsupported_command')
    return ('**,imei:'+imei+','+('J' if action=='inhibit_next_start' else 'K')).encode('ascii')


def safe(point, received):
    if not point or not received or time.time()-received>60:return False
    recorded=datetime.fromisoformat(point['recorded_at']).astimezone(timezone.utc).timestamp()
    return 0<=time.time()-recorded<=60 and point.get('quality')=='gps' and point.get('acc') is False and point.get('speed_kmh') is not None and point['speed_kmh']<=0.5


class Control:
    def __init__(self, receiver, uid):
        self.receiver=receiver;self.uid=uid

    async def execute(self, value):
        r=self.receiver
        if not isinstance(value,dict) or not re.fullmatch(r'\d{15}',str(value.get('imei',''))):raise ValueError('invalid_request')
        imei=value['imei'];writer=r.connections.get(imei);connected=bool(writer and not writer.is_closing())
        if value.get('operation')=='status':return dict(connected=connected)
        if value.get('operation')!='dispatch':raise ValueError('invalid_operation')
        if not re.fullmatch(r'[0-9a-f-]{36}',str(value.get('command_id',''))):raise ValueError('invalid_intention')
        deadline=value.get('deadline')
        if not isinstance(deadline,(int,float)) or not math.isfinite(deadline) or not 0<deadline-time.time()<=10:
            return dict(state='failed',detail='La intención venció; no se envió una orden.')
        frame=encode(imei,value.get('action'))
        route=mapping(r.mapping_path).get(imei)
        if not connected or not route or route['mode']!='forward' or any(route.get(k)!=value.get(k) for k in ('issuer','company_id','device_id')):
            return dict(state='failed',detail='El GPS no tiene una conexión activa autorizada; no queda una orden pendiente.')
        point,received=r.points.get(imei,(None,None))
        if value['action']=='inhibit_next_start' and not safe(point,received):
            return dict(state='failed',detail='El receptor no confirma GPS reciente, vehículo detenido y ACC apagado; no envió la orden.')
        if not r.store.claim_relay(value['command_id']):
            return dict(state='uncertain',detail='Esta intención ya se intentó; no se volvió a enviar.')
        if time.time()>=deadline:
            return dict(state='failed',detail='La intención venció antes de enviar; no queda pendiente.')
        # SQLite FULL receipt precedes writing. A crash can mean uncertain, never retry.
        try:
            writer.write(frame);await asyncio.wait_for(writer.drain(),timeout=2)
            return dict(state='sent_unconfirmed',detail='Orden enviada por la conexión TCP. Falta comprobar el resultado junto al vehículo.')
        except (OSError,ConnectionError,asyncio.TimeoutError):
            return dict(state='uncertain',detail='No se pudo confirmar la entrega completa. No habrá reintento automático.')

    async def connection(self, reader, writer):
        try:
            peer=writer.get_extra_info('socket').getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12)
            _,uid,_=struct.unpack('3i',peer)
            if uid!=self.uid:raise ValueError('unauthorized_peer')
            raw=await asyncio.wait_for(reader.readline(),timeout=2)
            if len(raw)>4096:raise ValueError('oversize')
            result=await self.execute(json.loads(raw))
        except (ValueError,KeyError,TypeError,ConnectionError,OSError,asyncio.TimeoutError):
            result=dict(state='failed',detail='Solicitud privada no autorizada o inválida.')
        try:
            writer.write(json.dumps(result).encode()+b'\n');await writer.drain()
        except (ConnectionError,OSError):pass
        finally:
            writer.close()
            try:await writer.wait_closed()
            except (ConnectionError,OSError):pass
