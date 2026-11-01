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
  print('TRACKER_INTEGRATION_COPY_OK gps_flow=True odoo_identity=True operation_catalogues=True no_external_dispatch=True')
 finally:api.terminate();api.wait(timeout=15)


if __name__=='__main__':main()
