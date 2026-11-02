"""Record an installer-confirmed starter circuit; never dispatch an actuator order."""
import argparse,base64,fcntl,hashlib,hmac,json,os,subprocess,time
from pathlib import Path
from urllib.request import Request,urlopen

p=argparse.ArgumentParser(description=__doc__);p.add_argument('facts',type=Path);p.add_argument('receipts',type=Path);p.add_argument('--installer',required=True);a=p.parse_args();assert os.geteuid()==0;os.umask(0o077)
facts=json.loads(a.facts.read_text(encoding='utf-8-sig'))['cerro'];key=json.loads(Path('/etc/tracker-bridge-keys.json').read_text())['CERRO_EL_PLOMO']
def call(path,body=None):
 t=int(time.time());enc=lambda v:base64.urlsafe_b64encode(v).rstrip(b'=');msg=enc(b'{"alg":"HS256","typ":"JWT"}')+b'.'+enc(json.dumps(dict(iss='CERRO_EL_PLOMO',aud='steps-tracker-v1',sub='commissioning:starter-wiring',company_id=facts['company_id'],role='manager',iat=t,exp=t+60)).encode());token=(msg+b'.'+enc(hmac.new(key.encode(),msg,hashlib.sha256).digest())).decode()
 with urlopen(Request('http://127.0.0.1:8000/v1/'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}),timeout=15) as r:return json.load(r)
with open('/run/lock/steps-environments.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX);asset=call('assets/'+facts['asset_id']);assert asset['plate']==facts['plate']
 inventory=call('configuration');devices=[d for d in inventory['items'] if d['asset_id']==facts['asset_id']];assert len(devices)==1 and devices[0]['commissioning']['mode']=='forward' and devices[0]['tracking_approved']
 root=a.receipts/str(int(time.time()));root.mkdir(parents=True,mode=0o700);(root/'before.json').write_text(json.dumps(dict(configuration=inventory,asset=asset),indent=2))
 with (root/'tracker_steps.dump').open('wb') as f:subprocess.run(['sudo','-u','postgres','pg_dump','-Fc','tracker_steps'],stdout=f,check=True)
 subprocess.run(['pg_restore','--file=/dev/null',str(root/'tracker_steps.dump')],check=True)
 response=call('assets/'+facts['asset_id']+'/starter-control/wiring',dict(starter_circuit='starter_motor',installer=a.installer,verified=True));status=call('assets/'+facts['asset_id']+'/starter-control')
 assert status['wiring_verified'];(root/'after.json').write_text(json.dumps(status,indent=2));print(json.dumps(dict(wiring_verified=True,connected=status['connected'],safe_to_inhibit=status['safe_to_inhibit'],physical_test_pending=True,orders_sent=False)))
