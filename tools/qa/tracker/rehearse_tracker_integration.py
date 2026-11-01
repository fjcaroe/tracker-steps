"""GPS + classic Odoo identity/catalogue rehearsal, only on a fresh private copy."""
import json
import os
import socket
import subprocess
import sys
import time
from urllib.request import Request,urlopen


def main():
 assert os.environ['DATABASE_URL'].rsplit('/',1)[-1].startswith('COBAN_QA_')
 from receivers.coban.rehearse import main as gps_flow
 gps_flow()
 from app.models.fleet import now
 from jose import jwt
 with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 api=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(port),'--log-level','error'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 base='http://127.0.0.1:'+str(port)
 try:
  for _ in range(80):
   try:
    with urlopen(base+'/health',timeout=1) as response:
     if response.status==200:break
   except OSError:time.sleep(.25)
  else:raise RuntimeError('Private API did not start')
  stamp=int(now().timestamp())
  identity=jwt.encode({'iss':'CERRO_EL_PLOMO','aud':'steps-tracker-v1','sub':'private-qa-operation','company_id':2,'role':'manager','iat':stamp,'exp':stamp+60},'test-only-coban-bridge',algorithm='HS256')
  request=Request(base+'/v1/classic-session',data=json.dumps({'login':'qa.invalid','name':'Private QA operation'}).encode(),headers={'Authorization':'Bearer '+identity,'Content-Type':'application/json'})
  with urlopen(request,timeout=10) as response:session=json.load(response)
  headers={'Authorization':'Bearer '+session['access_token']}
  for path in ('/auth/me','/auth/me/cost_centers','/machines','/drivers','/cost_centers','/fields','/sessions_recent?limit=100','/activities','/labors','/implements','/species','/varieties','/regions','/communes','/fundos','/sectors'):
   with urlopen(Request(base+path,headers=headers),timeout=10) as response:assert response.status==200
  # Protection is exercised ONLY against the synthetic vehicle in this fresh copy.
  from app.db.session import SessionLocal
  from app.models.fleet import Asset
  from urllib.error import HTTPError
  with SessionLocal() as db:
   asset=db.query(Asset).filter(Asset.source_id.like('private-coban:%')).order_by(Asset.created_at.desc()).first();assert asset
   asset_id=asset.id
  def security(path,method='GET',body=None,role='manager'):
   stamp=int(now().timestamp())
   token=jwt.encode({'iss':'CERRO_EL_PLOMO','aud':'steps-tracker-v1','sub':'private-qa-protection','company_id':2,'role':role,'iat':stamp,'exp':stamp+60},'test-only-coban-bridge',algorithm='HS256')
   request=Request(base+'/v1/'+path,method=method,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
   try:
    with urlopen(request,timeout=10) as response:return response.status,json.load(response)
   except HTTPError as exc:return exc.code,json.load(exc)
  policy={'asset_id':asset_id,'armed':True,'version':0,'reason':'Private copy parking test','contacts':['QA contact'],'allowed_hours_utc':[12],'zone':None}
  code,row=security('security/policies','PUT',policy);assert code==200 and row['version']==1
  assert security('security/policies','PUT',{**policy,'armed':False})[0]==409
  incident=security('security/incidents','POST',{'asset_id':asset_id,'type':'sos','reason':'Private copy SOS test only'})[1]
  policy.update(armed=False,version=1,reason='Private copy test completed')
  code,row=security('security/policies','PUT',policy);assert code==200 and row['version']==2
  snapshot=security('assets/'+asset_id)[1];assert snapshot['protection_state']=='incident_open' and snapshot['last_position']
  assert next(p for p in security('security/policies')[1] if p['asset_id']==asset_id)['armed'] is False
  assert security('security/policies','PUT',{**policy,'version':2},role='viewer')[0]==403
  assert security('security/incidents/'+incident['id'],'PATCH',{'state':'closed','reason':'Premature closure test'})[0]==409
  for state in ('acknowledged','closed'):
   assert security('security/incidents/'+incident['id'],'PATCH',{'state':state,'reason':'Private copy resolved test'})[0]==200
  assert security('assets/'+asset_id)[1]['protection_state']=='disarmed'
  print('PROTECTION_COPY_QA_OK arm=True stale_rejected=True disarm_with_open_sos=True acknowledge_close=True viewer_denied=True gps_preserved=True')
  print('TRACKER_INTEGRATION_COPY_OK gps_flow=True odoo_identity=True operation_catalogues=True no_external_dispatch=True')
 finally:api.terminate();api.wait(timeout=15)


if __name__=='__main__':main()
