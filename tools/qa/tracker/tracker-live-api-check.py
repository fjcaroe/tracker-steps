import json,time,urllib.request,urllib.error
from pathlib import Path
from jose import jwt
keys=json.loads(Path('/etc/tracker-bridge-keys.json').read_text())
def get(db,company,path):
 stamp=int(time.time()); token=jwt.encode({'iss':db,'aud':'steps-tracker-v1','sub':'release-check','iat':stamp,'exp':stamp+60,'company_id':company,'role':'manager'},keys[db],algorithm='HS256')
 req=urllib.request.Request('http://127.0.0.1:8000/v1/'+path,headers={'Authorization':'Bearer '+token})
 try:
  with urllib.request.urlopen(req) as res: return res.status,json.load(res)
 except urllib.error.HTTPError as e: return e.code,None
all_ids={}
for db in keys:
 for company in ([1,2,3,4] if db=='CERRO_EL_PLOMO' else [1]):
  status,data=get(db,company,'fleet/snapshot'); assert status==200,(db,status)
  ids={a['asset_id'] for a in data['items']}; all_ids[(db,company)]=ids
  print(json.dumps({'database':db,'company':company,'assets':len(ids),'result':'OK'}))
for (db,company),ids in all_ids.items():
 for (otherdb,othercompany),otherids in all_ids.items():
  if (db,company)==(otherdb,othercompany): continue
  assert not ids.intersection(otherids)
  if otherids: assert get(db,company,'assets/'+next(iter(otherids)))[0]==404
assert get('LAB_TAREAS',999,'fleet/snapshot')[0]==401
print('CROSS_TENANT_ISOLATION_OK')
