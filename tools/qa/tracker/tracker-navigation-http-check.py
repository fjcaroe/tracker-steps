import json
import requests
from datetime import datetime, timezone, timedelta
from odoo import http
# Executed by odoo shell using the target configuration. The transient session
# stays on the server and is removed immediately after the HTTP assertions.
user=env.ref('base.user_admin')
assert user.active
session=http.root.session_store.new()
session.update({'db':env.cr.dbname,'login':user.login,'uid':user.id,'context':dict(user.with_user(user).context_get()),'session_token':user._compute_session_token(session.sid)})
http.root.session_store.save(session)
ports={'LAB_TAREAS':8075,'STEPS_DEMO':8080,'CERRO_EL_PLOMO':8082}
hosts={'LAB_TAREAS':'desarrollo.stepsapp.cl','STEPS_DEMO':'demo.stepsapp.cl','CERRO_EL_PLOMO':'cerroelplomo.stepsapp.cl'}
client=requests.Session()
client.cookies.set('session_id',session.sid)
client.headers['Host']=hosts[env.cr.dbname]
base='http://127.0.0.1:'+str(ports[env.cr.dbname])
try:
 context=client.get(base+'/steps_tracker/context',timeout=30)
 assert context.status_code==200,(context.status_code,context.text[:120])
 data=context.json(); assert data['role']=='manager'
 snapshot=client.get(base+'/steps_tracker/api/fleet/snapshot',timeout=30)
 assert snapshot.status_code==200,(snapshot.status_code,snapshot.text[:120])
 result=snapshot.json()
 assert result['tenant']==data['company']
 for asset in result['items'][:1]:
  trail=client.get(base+'/steps_tracker/api/assets/'+asset['asset_id']+'/positions',params={'current_assignment':'true','since':(datetime.now(timezone.utc)-timedelta(hours=24)).isoformat(),'limit':500},timeout=30)
  assert trail.status_code==200,trail.status_code
  assert 'items' in trail.json() and 'next_cursor' in trail.json()
 config_response=client.get(base+'/steps_tracker/api/configuration',timeout=30)
 assert config_response.status_code==200,config_response.status_code
 assert 'items' in config_response.json() and 'reminders' in config_response.json()
 zones_response=client.get(base+'/steps_tracker/api/zones',timeout=30)
 assert zones_response.status_code==200 and isinstance(zones_response.json(),list)
 invalid=client.post(base+'/steps_tracker/api/zones',data={'csrf_token':data['csrf_token'],'method':'POST','payload':json.dumps({'name':'QA invalid, must not persist','vertices':[]})},timeout=30)
 assert invalid.status_code==422,invalid.status_code
 assert client.get(base+'/steps_tracker/api/zones',timeout=30).json()==zones_response.json()
 assert env.ref('step_tracker_portal.action_zones').url=='/web_tracker/#zones'
 assert env.ref('step_tracker_portal.menu_zones').id in env['ir.ui.menu'].with_user(user)._visible_menu_ids()
 root_menu=env.ref('step_tracker_odoo.menu_step_tracker_gps_root')
 assert root_menu.active and not root_menu.parent_id
 assert root_menu.action._name=='ir.actions.act_url'
 assert root_menu.action.url=='/web_tracker/#home'
 assert env.ref('step_tracker_portal.menu_home').id in env['ir.ui.menu'].with_user(user)._visible_menu_ids()
 # CSRF blocks forged writes; no mutation should happen.
 rejected=client.post(base+'/steps_tracker/api/view-preferences/qa-forged',data={'method':'PUT','payload':'{}'},timeout=30)
 assert rejected.status_code==400,rejected.status_code
 assert client.get(base+'/steps_tracker/api/ingest/positions',timeout=30).status_code==403
 print(json.dumps({'database':env.cr.dbname,'authenticated_context':'OK','csrf':'OK','ingest_proxy_block':'OK','assets':result['total'],'recent_trail':'OK' if result['items'] else 'NO_ASSETS','zones':'OK','configuration':'OK','odoo_launcher':'OK'}))
finally:
 http.root.session_store.delete(session)
 env.cr.rollback()
