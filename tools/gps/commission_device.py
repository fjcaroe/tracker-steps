"""Register one user-supplied Cerro GPS through the existing API, capture only.

SSH/root operation. Input and receipts are private JSON outside the checkout.
No vehicle is invented, no tracking approved and no device command dispatched.
"""
import argparse
import base64
from datetime import datetime,timezone
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import time
from urllib.request import Request,urlopen


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('--apply',action='store_true');p.add_argument('--receipts',type=Path,required=True);args=p.parse_args()
 assert os.geteuid()==0;os.umask(0o077)
 data=json.loads(args.input.read_text(encoding='utf-8-sig'));assert re.fullmatch(r'\d{15}',data['imei'])
 assert type(data['company_id']) is int and data['company_id']>0
 key=json.loads(Path('/etc/tracker-bridge-keys.json').read_text())['CERRO_EL_PLOMO']
 def call(path,body=None):
  stamp=int(time.time());claims={'iss':'CERRO_EL_PLOMO','aud':'steps-tracker-v1','sub':'commissioning:codex','company_id':data['company_id'],'role':'manager','iat':stamp,'exp':stamp+60}
  def enc(value):return base64.urlsafe_b64encode(value).rstrip(b'=')
  message=enc(b'{"alg":"HS256","typ":"JWT"}')+b'.'+enc(json.dumps(claims).encode())
  token=(message+b'.'+enc(hmac.new(key.encode(),message,hashlib.sha256).digest())).decode()
  request=Request('http://127.0.0.1:8000/v1/'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
  with urlopen(request,timeout=15) as response:return json.load(response)
 with open('/run/lock/steps-environments.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  assert call('fleet/snapshot?limit=1')['tenant']==data['expected_company'],'Company identity differs; do not guess'
  inventory=call('configuration');existing=next((d for d in inventory['items'] if d['imei']==data['imei']),None)
  if existing:assert existing['phone']==data['phone'],'Registered SIM differs; review before changing'
  if not args.apply:print(json.dumps({'dry_run':True,'already_registered':bool(existing),'requested_mode':'capture'}));return
  args.receipts.mkdir(parents=True,exist_ok=True,mode=0o700);args.receipts.chmod(0o700)
  stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
  (args.receipts/(stamp+'-before.json')).write_text(json.dumps(inventory,indent=2))
  if not existing:
   fields=('imei','brand','model','phone','operator','plan_type','notes')
   call('configuration/devices',{name:data[name] for name in fields if name in data})
   existing=next(d for d in call('configuration')['items'] if d['imei']==data['imei'])
  if existing['commissioning']['mode']=='disabled':
   call('configuration/devices/'+existing['id']+'/commissioning',{'mode':'capture','version':existing['version'],'reason':'Equipo y SIM informados por el usuario; diagnóstico previo a instalación física.'})
  after=call('configuration');row=next(d for d in after['items'] if d['imei']==data['imei'])
  assert row['phone']==data['phone'] and row['commissioning']['mode'] in ('capture','forward')
  (args.receipts/(stamp+'-after.json')).write_text(json.dumps(after,indent=2))
  print(json.dumps({'registered':True,'receiver_mode':row['commissioning']['mode'],'assigned':bool(row['asset_id']),'tracking_approved':row['tracking_approved']}))


if __name__=='__main__':main()
