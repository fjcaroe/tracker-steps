"""Ephemeral browser proof for the specific existing personal account; no business writes."""
import json,os
from pathlib import Path
import requests
from odoo import http
proof=Path(os.environ['PERSONAL_SESSION_PROOF'])
if os.environ.get('PERSONAL_SESSION_CLEANUP')=='1':
 session=http.root.session_store.get(json.loads(proof.read_text())['session_id']);http.root.session_store.delete(session);proof.unlink();print('PERSONAL_BROWSER_SESSION_REMOVED')
else:
 facts=json.loads(Path(os.environ['PERSONAL_FACTS']).read_text());user=env['res.users'].search([('login','=',facts['login']),('active','=',True)]);assert len(user)==1
 target=env.cr.dbname=='LAB_TAREAS';assert target or env.cr.dbname=='CERRO_EL_PLOMO'
 company=user.company_id if target else env['res.company'].browse(facts['source_company']);assert company in user.company_ids
 if target:
  links=env['step.tracker.asset.link'].with_user(user).with_context(allowed_company_ids=company.ids).search([('company_id','=',company.id),('asset_id','=',facts['asset_id']),('active','=',True)]);assert len(links)==1
  assert links.vehicle_id.license_plate==facts['plate'] and links.vehicle_id.odometer==max(r['value'] for r in facts['readings'])
 session=http.root.session_store.new();session.update({'db':env.cr.dbname,'login':user.login,'uid':user.id,'context':dict(user.with_user(user).context_get(),allowed_company_ids=company.ids),'session_token':user._compute_session_token(session.sid)});http.root.session_store.save(session)
 host='desarrollo.stepsapp.cl' if target else 'cerroelplomo.stepsapp.cl';port=8075 if target else 8082
 proof.write_text(json.dumps({'session_id':session.sid,'company_id':company.id,'host':host}));proof.chmod(0o600)
 client=requests.Session();client.cookies.set('session_id',session.sid);client.cookies.set('cids',str(company.id));client.headers['Host']=host
 base='http://127.0.0.1:'+str(port);ctx=client.get(base+'/steps_tracker/context',timeout=30);assert ctx.status_code==200 and ctx.json()['user_id']==user.id
 config=client.get(base+'/steps_tracker/api/configuration',timeout=30);assert config.status_code==200;items=config.json()['items'];assert len(items)==(1 if target else 4)
 asset=client.get(base+'/steps_tracker/api/assets/'+facts['asset_id'],timeout=30);assert asset.status_code==(200 if target else 404)
 if target:assert asset.json()['last_position'] and config.json()['receiver']['online']
 proof.write_text(json.dumps({'session_id':session.sid,'company_id':company.id,'host':host}));proof.chmod(0o600)
 print('PERSONAL_BROWSER_READY target='+str(target)+' correct_user=True source_isolated=True registry_count='+str(len(items)))
env.cr.rollback()
