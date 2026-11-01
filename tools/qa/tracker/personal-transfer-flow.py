"""Synthetic TCP fix into a migrated private API copy, never a live service."""
import json,os,socket,subprocess,sys,tempfile,time
from pathlib import Path
from datetime import datetime,timezone
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from receivers.coban.server import Receiver,poll_configuration,flush,token
from receivers.coban.store import Store
from jose import jwt
plan=json.loads(Path(os.environ['PERSONAL_PLAN']).read_text());assert os.environ['DATABASE_URL'].split('/')[-1].startswith('PERSONAL_GPS_QA_')
keys={'CERRO_EL_PLOMO':'private-source-test-key','LAB_TAREAS':'private-target-test-key'};os.environ['TRACKER_BRIDGE_KEYS']=json.dumps(keys)
with tempfile.TemporaryDirectory() as directory:
 root=Path(directory);policy=root/'policy.json';policy.write_text(json.dumps([{'issuer':'LAB_TAREAS','company_id':plan['target_company']}]))
 os.environ['TRACKER_COBAN_TENANTS_FILE']=str(policy)
 with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 api=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port),'--log-level','error'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 base='http://127.0.0.1:'+str(port)
 def get(path,issuer,company):
  stamp=int(time.time());identity=jwt.encode({'iss':issuer,'aud':'steps-tracker-v1','sub':'private-copy-review','company_id':company,'role':'manager','iat':stamp,'exp':stamp+60},keys[issuer],algorithm='HS256')
  r=Request(base+'/v1/'+path,headers={'Authorization':'Bearer '+identity})
  try:
   with urlopen(r,timeout=10) as response:return response.status,json.load(response)
  except HTTPError as e:return e.code,json.load(e)
 try:
  for _ in range(100):
   try:
    with urlopen(base+'/health',timeout=1) as r:
     if r.status==200:break
   except OSError:time.sleep(.2)
  else:raise RuntimeError('Private migration API failed startup')
  assert get('assets/'+plan['asset_id'],'CERRO_EL_PLOMO',plan['source_company'])[0]==404
  assert get('assets/'+plan['asset_id'],'LAB_TAREAS',plan['target_company'])[0]==200
  mapping=root/'mapping.json';mapping.write_text('{}');keyfile=root/'keys.json';keyfile.write_text(json.dumps({'issuers':keys}));store=Store(root/'inbox.sqlite')
  cfg={'api':base,'mapping':str(mapping),'key_file':str(keyfile),'tenants':[{'issuer':'CERRO_EL_PLOMO','company_id':plan['source_company']},{'issuer':'LAB_TAREAS','company_id':plan['target_company']}]}
  poll_configuration(store,cfg);routes=json.loads(mapping.read_text());assert len(routes)==5 and routes[plan['imei']]['issuer']=='LAB_TAREAS'
  receiver=Receiver(store,mapping);assert receiver.process(('##,imei:'+plan['imei']+',A;').encode())==b'LOAD'
  now=datetime.now(timezone.utc);frame=('imei:'+plan['imei']+',tracker,'+now.strftime('%y%m%d%H%M%S')+',,F,'+now.strftime('%H%M%S')+'.000,A,3300.0000,S,07000.0000,W,10.00,0,,1,0,;').encode()
  receiver.process(frame);flush(store,cfg);assert store.status()['queued']==0
  result=get('assets/'+plan['asset_id'],'LAB_TAREAS',plan['target_company'])[1];assert result['last_position'] and result['last_position']['lat']==-33
  poll_configuration(store,cfg)
  assert len(get('configuration','CERRO_EL_PLOMO',plan['source_company'])[1]['items'])==4
  assert len(get('configuration','LAB_TAREAS',plan['target_company'])[1]['items'])==1
  assert get('configuration','LAB_TAREAS',plan['target_company'])[1]['receiver']['online']
  print('PERSONAL_TRANSFER_TCP_COPY_OK source_isolated=True target_receives=True registrations=4+1 no_live_writes=True')
 finally:
  api.terminate()
  try:api.wait(timeout=10)
  except subprocess.TimeoutExpired:api.kill();api.wait()
