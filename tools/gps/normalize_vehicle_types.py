"""Normalize explicitly confirmed GPS classes; fresh copy, same API route, backup.

Private plan: issuer, company_id, assets [{asset_id, plate, type}]. No hardware
orders, vehicle associations, permissions or native model definitions change.
"""
import argparse,base64,fcntl,hashlib,hmac,json,os,subprocess,sys,time
from pathlib import Path
from urllib.request import Request,urlopen

def run(*args,**kwargs):return subprocess.run(list(map(str,args)),check=True,**kwargs)

def copied(plan):
 import dotenv
 dotenv.load_dotenv=lambda *a,**k:False
 from app.main import app  # load the complete shared SQLAlchemy registry
 from app.db.session import SessionLocal
 from app.models.fleet import Tenant,Asset,Position,Assignment
 from app.routers.fleet import edit_asset,AssetDetails
 with SessionLocal() as db:
  tenant=db.query(Tenant).filter_by(issuer=plan['issuer'],company_id=plan['company_id']).one()
  ctx=dict(tenant_id=tenant.id,user_id='qa:vehicle-class',role='manager',asset_ids=None)
  count=db.query(Position).count();assignments=[(r.id,r.asset_id,r.device_id) for r in db.query(Assignment).all()]
  for item in plan['assets']:
   row=db.query(Asset).filter_by(id=item['asset_id'],tenant_id=tenant.id).one();assert row.plate==item['plate']
   fields={k:getattr(row,k) for k in ('name','plate','type','cost_center','responsible')};fields['type']=item['type']
   edit_asset(row.id,AssetDetails(**fields),ctx,db);db.refresh(row);assert row.type==item['type']
   edit_asset(row.id,AssetDetails(**fields),ctx,db);db.refresh(row);assert row.type==item['type']
  assert db.query(Position).count()==count
  assert [(r.id,r.asset_id,r.device_id) for r in db.query(Assignment).all()]==assignments
 print('VEHICLE_TYPE_COPY_OK history_preserved=True associations_preserved=True')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['qa','apply','copy']);p.add_argument('source',type=Path);p.add_argument('plan',type=Path);p.add_argument('root',type=Path);a=p.parse_args()
 plan=json.loads(a.plan.read_text());assert plan['issuer']=='CERRO_EL_PLOMO' and plan['company_id']==2
 assert 0<len(plan['assets'])<=10 and all(r['type'] in ('pickup','car','truck','van','motorcycle','tractor','machinery','other') for r in plan['assets'])
 if a.action=='copy':assert os.environ['DATABASE_URL'].rsplit('/',1)[-1].startswith('TYPE_QA_');copied(plan);return
 assert os.geteuid()==0;os.umask(0o077)
 source=a.source.resolve();commit=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip();assert not subprocess.check_output(['git','-C',str(source),'status','--porcelain','--untracked-files=no'],text=True).strip()
 root=a.root/commit;root.mkdir(parents=True,exist_ok=True);signature=hashlib.sha256(a.plan.read_bytes()).hexdigest()
 with open('/run/lock/steps-environments.lock','a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX);stamp=str(int(time.time()));dump=root/(a.action+'-'+stamp+'.dump')
  with dump.open('wb') as out:run('sudo','-u','postgres','pg_dump','-Fc','tracker_steps',stdout=out)
  run('pg_restore','--file=/dev/null',dump)
  if a.action=='qa':
   db='TYPE_QA_'+stamp;run('sudo','-u','postgres','createdb',db)
   try:
    with dump.open('rb') as inp:run('sudo','-u','postgres','pg_restore','--no-owner','--no-acl','-d',db,stdin=inp)
    # Only this nonsecret plan is copied for the isolated PostgreSQL OS account.
    private=Path('/tmp/type-qa-'+stamp+'.json');private.write_bytes(a.plan.read_bytes());private.chmod(0o644)
    try:
     with (root/'qa.log').open('wb') as log:run('sudo','-u','postgres','env','DATABASE_URL=postgresql+psycopg2:///'+db,'JWT_SECRET=copy-only','PYTHONPATH='+str(source/'backend/tracker_py'),'/opt/fernando_odoo18/apis/backend/tracker_py/.venv/bin/python',Path(__file__),'copy',source,private,root,stdout=log,stderr=subprocess.STDOUT)
    finally:private.unlink(missing_ok=True)
    assert 'VEHICLE_TYPE_COPY_OK' in (root/'qa.log').read_text();(root/'qa.json').write_text(json.dumps(dict(commit=commit,plan_sha=signature,fresh_copy=True,history_preserved=True)))
   finally:run('sudo','-u','postgres','dropdb','--if-exists',db)
   print('VEHICLE_TYPE_QA_OK');return
  proof=json.loads((root/'qa.json').read_text());assert proof['commit']==commit and proof['plan_sha']==signature
  key=json.loads(Path('/etc/tracker-bridge-keys.json').read_text())[plan['issuer']]
  def call(path,body=None):
   stamp=int(time.time());data=dict(iss=plan['issuer'],aud='steps-tracker-v1',sub='ops:vehicle-class',company_id=plan['company_id'],role='manager',iat=stamp,exp=stamp+60)
   enc=lambda b:base64.urlsafe_b64encode(b).rstrip(b'=');message=enc(b'{"alg":"HS256","typ":"JWT"}')+b'.'+enc(json.dumps(data).encode());token=(message+b'.'+enc(hmac.new(key.encode(),message,hashlib.sha256).digest())).decode()
   req=Request('http://127.0.0.1:8000/v1/'+path,method='PATCH' if body else 'GET',data=json.dumps(body).encode() if body else None,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
   with urlopen(req,timeout=20) as response:return json.load(response)
  changes=[]
  for item in plan['assets']:
   row=call('assets/'+item['asset_id']);assert row['plate']==item['plate'];fields={k:row[k] for k in ('name','plate','type','cost_center','responsible')}
   before=dict(fields);fields['type']=item['type']
   if before!=fields:call('assets/'+item['asset_id'],fields)
   result=call('assets/'+item['asset_id']);assert all(result[k]==v for k,v in fields.items())
   changes.append(dict(asset_id=item['asset_id'],before=before,after=fields))
  (root/'delivery.json').write_text(json.dumps(dict(commit=commit,backup=str(dump),changes=changes,physical_commands_sent=False),indent=2));print('VEHICLE_TYPES_READY')
if __name__=='__main__':main()
