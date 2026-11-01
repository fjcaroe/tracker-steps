"""Coban TCP listener with per-IMEI opt-in and a private, durable API outbox."""
import argparse
import asyncio
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import time
from urllib.request import Request,urlopen
from .protocol import Framer,InvalidFrame,identify,decode,source_id
from .store import Store


def mapping(path):
    values=json.loads(Path(path).read_text())
    if not isinstance(values,dict):raise ValueError('invalid_mapping')
    for imei,value in values.items():
        if not re.fullmatch(r'\d{15}',imei):raise ValueError('invalid_mapping')
        if value.get('issuer') not in ('CERRO_EL_PLOMO','LAB_TAREAS') or type(value.get('company_id')) is not int:raise ValueError('wrong_tenant')
        if value.get('mode') not in ('capture','forward'):raise ValueError('invalid_mode')
        if value['mode']=='forward' and not re.fullmatch(r'[0-9a-f-]{36}',value.get('device_id','')):raise ValueError('missing_device')
    return values


class Receiver:
    def __init__(self,store,mapping_path):
        self.store=store;self.mapping_path=mapping_path;self.active=0;self.per_ip={}

    def process(self,frame):
        imei,kind=identify(frame)
        route=mapping(self.mapping_path).get(imei)
        if route is None:
            self.store.count('unknown_identity');raise InvalidFrame('unknown_identity')
        self.store.count('known_'+kind)
        self.store.observe(imei)
        if kind=='login':return b'LOAD'
        if kind=='heartbeat':return b'ON'
        try:point=decode(frame)
        except InvalidFrame:
            self.store.observe(imei,error='decode_rejected')
            self.store.capture(imei,frame,'unsupported_or_invalid');self.store.count('decode_rejected');return None
        if point is None:
            self.store.observe(imei,error='no_valid_gps')
            self.store.count('no_valid_gps');return None
        self.store.observe(imei,point)
        if route['mode']=='capture':
            self.store.capture(imei,frame,'commissioning');self.store.count('capture_only');return None
        point.update(device_id=route['device_id'],source_id=source_id(frame))
        try:self.store.enqueue(imei,point['source_id'],{'issuer':route['issuer'],'company_id':route['company_id'],'device_id':route['device_id']},point)
        except RuntimeError:
            self.store.observe(imei,error='queue_full');raise
        self.store.count('durably_received')
        return ('**,imei:'+imei+',E;').encode() if point['sos'] else None

    async def connection(self,reader,writer):
        peer=writer.get_extra_info('peername');ip=peer[0] if peer else 'unknown'
        if self.active>=64 or self.per_ip.get(ip,0)>=8:
            writer.close();return
        self.active+=1;self.per_ip[ip]=self.per_ip.get(ip,0)+1
        framer=Framer()
        window=time.monotonic();messages=0;bound=None
        try:
            while True:
                data=await asyncio.wait_for(reader.read(4096),timeout=180)
                if not data:break
                for frame in framer.feed(data):
                    if time.monotonic()-window>60:window=time.monotonic();messages=0
                    messages+=1
                    if messages>120:raise InvalidFrame('rate_limit')
                    imei,_=identify(frame)
                    if bound is not None and imei!=bound:raise InvalidFrame('identity_changed')
                    bound=imei
                    response=self.process(frame)
                    if response:writer.write(response);await writer.drain()
        except (TimeoutError,asyncio.TimeoutError,ConnectionError,InvalidFrame,UnicodeError,ValueError,OSError,RuntimeError):
            self.store.count('connection_rejected')
        finally:
            self.active-=1;self.per_ip[ip]-=1
            if not self.per_ip[ip]:del self.per_ip[ip]
            writer.close()
            try:await writer.wait_closed()
            except ConnectionError:pass


def token(issuer,company,key):
    def b64(value):return base64.urlsafe_b64encode(value).rstrip(b'=')
    stamp=int(time.time())
    claims={'iss':issuer,'aud':'steps-tracker-v1','sub':'receiver:coban-gps103','company_id':company,'role':'ingestor','iat':stamp,'exp':stamp+60}
    message=b64(b'{"alg":"HS256","typ":"JWT"}')+b'.'+b64(json.dumps(claims,separators=(',',':')).encode())
    return (message+b'.'+b64(hmac.new(key.encode(),message,hashlib.sha256).digest())).decode()


def issuer_keys(config):
    value=json.loads(Path(config['key_file']).read_text())
    keys=value.get('issuers') if 'issuers' in value else {value['issuer']:value['key']}
    if not isinstance(keys,dict) or not keys or set(keys)-{'CERRO_EL_PLOMO','LAB_TAREAS'} or not all(isinstance(k,str) and k for k in keys.values()):raise ValueError('wrong_issuer')
    return keys


def flush(store,config):
    routes=mapping(config['mapping'])
    keys=issuer_keys(config)
    for source,imei,stored,payload,attempts in store.pending():
        route=json.loads(stored);current=routes.get(imei)
        # Never reroute an old point under a new device/company mapping.
        if current is None or current.get('mode')!='forward' or any(current.get(k)!=v for k,v in route.items()):
            store.result(source,False,attempts);continue
        try:
            request=Request(config['api']+'/v1/ingest/positions',data=payload.encode(),headers={
                'Authorization':'Bearer '+token(route['issuer'],route['company_id'],keys[route['issuer']]),'Content-Type':'application/json'})
            with urlopen(request,timeout=8) as response:receipt=json.load(response)
            accepted=bool(receipt.get('id'))
        except (OSError,ValueError,KeyError):accepted=False
        store.result(source,accepted,attempts)
        store.count('api_delivered' if accepted else 'api_retry')


def poll_configuration(store,config):
    """Refresh only successfully polled companies; outages keep the durable cache."""
    routes=mapping(config['mapping'])
    keys=issuer_keys(config)
    for target in config.get('tenants',[{'issuer':'CERRO_EL_PLOMO','company_id':c} for c in config.get('companies',[])]):
        try:
            issuer,company=target['issuer'],target['company_id']
            imeis=[imei for imei,route in routes.items() if route['company_id']==company and route['issuer']==issuer]
            request=Request(config['api']+'/v1/receiver/poll',data=json.dumps({'release':'coban-personal-split-1','observations':store.observations(imeis)}).encode(),headers={
                'Authorization':'Bearer '+token(issuer,company,keys[issuer]),'Content-Type':'application/json'})
            with urlopen(request,timeout=8) as response:result=json.load(response)
            replacement={row['imei']:{k:row[k] for k in ('issuer','company_id','device_id','mode')} for row in result['devices']}
            if any(row['company_id']!=company or row['issuer']!=issuer for row in replacement.values()):raise ValueError('wrong_tenant')
            updated={imei:route for imei,route in routes.items() if route['company_id']!=company or route['issuer']!=issuer}
            if set(updated)&set(replacement):raise ValueError('identity_collision')
            updated.update(replacement)
            temporary=Path(config['mapping']+'.new');temporary.write_text(json.dumps(updated));os.chmod(temporary,0o600)
            mapping(temporary);os.replace(temporary,config['mapping']);routes=updated
            store.count('configuration_polled')
        except (OSError,ValueError,KeyError,TypeError):store.count('configuration_retry')


async def run(config,store):
    receiver=Receiver(store,config['mapping'])
    async def worker():
        last_poll=0
        while True:
            try:
                if (config.get('companies') or config.get('tenants')) and time.monotonic()-last_poll>=5:
                    await asyncio.to_thread(poll_configuration,store,config);last_poll=time.monotonic()
                await asyncio.to_thread(flush,store,config)
            except (OSError,ValueError):store.count('worker_config_error')
            await asyncio.sleep(2)
    server=await asyncio.start_server(receiver.connection,config.get('host','0.0.0.0'),config.get('port',5001),limit=16384)
    print('COBAN_LISTENING port='+str(config.get('port',5001)),flush=True)
    async with server:await asyncio.gather(server.serve_forever(),worker())


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);parser.add_argument('--status',action='store_true')
    args=parser.parse_args();os.umask(0o077)
    config=json.loads(Path(args.config).read_text());mapping(config['mapping'])
    if config['api']!='http://127.0.0.1:8000':raise ValueError('private_api_required')
    store=Store(config['database'])
    if args.status:
        print(json.dumps({'service':'steps-coban','protocol':'gps103-ascii','registered_identities':len(mapping(config['mapping'])),**store.status()}));return
    asyncio.run(run(config,store))


if __name__=='__main__':main()
