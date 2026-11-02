"""Associate an existing physical GPS with a user-confirmed plate using the API.

Private input/receipts only. Never guesses a Fleet model or promotes old bench
coordinates into vehicle history. Forwarding requires a fresh post-assignment
GPS fix and the explicit reviewed flag. No SMS or physical controls are sent.
"""
import argparse,base64,fcntl,hashlib,hmac,json,os,re,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('plan',type=Path);p.add_argument('receipts',type=Path);p.add_argument('--apply',action='store_true');p.add_argument('--approve-reviewed',action='store_true');p.add_argument('--wait-seconds',type=int,default=40);a=p.parse_args()
 assert os.geteuid()==0 and 0<=a.wait_seconds<=60;os.umask(0o077)
 data=json.loads(a.plan.read_text(encoding='utf-8-sig'));assert re.fullmatch(r'\d{15}',data['imei']) and re.fullmatch(r'[A-Z0-9]{5,8}',data['plate']) and type(data['company_id']) is int
 key=json.loads(Path('/etc/tracker-bridge-keys.json').read_text())['CERRO_EL_PLOMO']
 def call(path,body=None):
  stamp=int(time.time());claims=dict(iss='CERRO_EL_PLOMO',aud='steps-tracker-v1',sub='commissioning:codex',company_id=data['company_id'],role='manager',iat=stamp,exp=stamp+60)
  enc=lambda v:base64.urlsafe_b64encode(v).rstrip(b'=');message=enc(b'{"alg":"HS256","typ":"JWT"}')+b'.'+enc(json.dumps(claims).encode());token=(message+b'.'+enc(hmac.new(key.encode(),message,hashlib.sha256).digest())).decode()
  request=Request('http://127.0.0.1:8000/v1/'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
  with urlopen(request,timeout=20) as response:return json.load(response)
 norm=lambda value:re.sub('[^A-Z0-9]','',(value or '').upper())
 with open('/run/lock/steps-environments.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  fleet=call('fleet/snapshot?limit=500');assert fleet['tenant']==data['expected_company'] and fleet['total']<=500
  inventory=call('configuration');matches=[r for r in inventory['items'] if r['imei']==data['imei']];assert len(matches)==1
  row=matches[0];assert row['phone']==data['phone'],'SIM differs; review before changing anything'
  assets=[r for r in fleet['items'] if norm(r['plate'])==data['plate']];assert len(assets)<=1,'Duplicate plate requires review'
  if row['asset_id']:assert assets and row['asset_id']==assets[0]['asset_id'],'GPS already belongs to a different vehicle'
  if not a.apply:print(json.dumps(dict(eligible=True,existing_asset=bool(assets),assigned=bool(row['asset_id']),mode=row['commissioning']['mode'])));return
  root=a.receipts/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');root.mkdir(mode=0o700,parents=True)
  (root/'before.json').write_text(json.dumps(dict(fleet=fleet,configuration=inventory),indent=2))
  with (root/'tracker_steps.dump').open('wb') as out:subprocess.run(['sudo','-u','postgres','pg_dump','-Fc','tracker_steps'],stdout=out,check=True)
  subprocess.run(['pg_restore','--file=/dev/null',str(root/'tracker_steps.dump')],check=True)
  if not assets:
   created=call('assets',dict(name=data['plate'],plate=data['plate'],type='vehicle'))
   asset_id=created['asset_id']
  else:asset_id=assets[0]['asset_id']
  if row['asset_id'] is None:
   call('configuration/devices/'+row['id']+'/assignment',dict(asset_id=asset_id,version=row['version'],reason='El usuario confirmó la unidad física y patente durante su instalación.'))
   row=next(r for r in call('configuration')['items'] if r['imei']==data['imei'])
   # Start a new installation check. Old bench observations remain in the
   # private receipt/inbox and cannot appear as the newly installed car's fix.
   call('configuration/devices/'+row['id']+'/commissioning',dict(mode='capture',version=row['version'],reason='Instalación en vehículo confirmada; esperar nueva posición posterior a la asociación.'))
  end=time.monotonic()+a.wait_seconds
  while True:
   inventory=call('configuration');row=next(r for r in inventory['items'] if r['imei']==data['imei'])
   d=row['commissioning'];fix=d.get('fix_at');received=d.get('fix_received_at')
   if a.approve_reviewed and d['mode']!='forward' and fix and received and time.time()-datetime.fromisoformat(fix.replace('Z','+00:00')).timestamp()<300 and time.time()-datetime.fromisoformat(received.replace('Z','+00:00')).timestamp()<300:
    call('configuration/devices/'+row['id']+'/commissioning',dict(mode='forward',version=row['version'],verified=True,reason='IMEI/SIM y patente confirmados por el usuario; posición TCP válida y reciente posterior a la asociación.'))
    continue
   snapshot=call('assets/'+asset_id)
   if (d['mode']=='forward' and snapshot.get('last_position')) or time.monotonic()>=end:break
   time.sleep(2)
  assert row['asset_id']==asset_id
  (root/'after.json').write_text(json.dumps(dict(configuration=inventory,asset=snapshot),indent=2))
  result=dict(associated=True,asset_id=asset_id,receiver_mode=row['commissioning']['mode'],tracking_approved=row['tracking_approved'],vehicle_position_visible=bool(snapshot.get('last_position')),last_contact=row['commissioning'].get('last_seen_at'),receipt=str(root))
  (root/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
if __name__=='__main__':main()
