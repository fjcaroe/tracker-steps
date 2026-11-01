"""Run through the target's Odoo shell; ephemeral browser session stays private.

GPS_BROWSER_PROOF points outside the checkout. Cleanup deletes this session.
No production device, vehicle, user, permission or configuration is changed.
"""
import json
import os
from pathlib import Path
import requests
from odoo import http

proof=Path(os.environ['GPS_BROWSER_PROOF'])
if os.environ.get('GPS_REVIEW_CLEANUP')=='1':
    session=http.root.session_store.get(json.loads(proof.read_text())['session_id'])
    http.root.session_store.delete(session);proof.unlink()
    print('GPS_NATIVE_SESSION_REMOVED')
else:
    cerro=env.cr.dbname=='CERRO_EL_PLOMO'
    company=env['res.company'].search([('vat','=','76943293-0'),('parent_id','=',False)]) if cerro else env.ref('base.main_company')
    assert len(company)==1
    users=env['res.users'].search([('active','=',True),('share','=',False),('id','!=',1),('company_ids','in',company.ids)],order='id')
    user=users.filtered(lambda u:u.has_group('base.group_system'))[:1];assert user
    menu=env.ref('step_tracker_portal.menu_configuration')
    assert menu.id in env['ir.ui.menu'].with_user(user)._visible_menu_ids()
    assert menu.action.url=='/web_tracker/#settings'
    module=env['ir.module.module'].search([('name','=','step_tracker_portal')]);assert module.state=='installed'
    session=http.root.session_store.new()
    session.update({'db':env.cr.dbname,'login':user.login,'uid':user.id,'context':dict(user.with_user(user).context_get(),allowed_company_ids=company.ids),'session_token':user._compute_session_token(session.sid)})
    http.root.session_store.save(session)
    host='cerroelplomo.stepsapp.cl' if cerro else 'desarrollo.stepsapp.cl'
    port=8082 if cerro else 8075
    client=requests.Session();client.cookies.set('session_id',session.sid);client.cookies.set('cids',str(company.id));client.headers['Host']=host
    base='http://127.0.0.1:'+str(port)
    response=client.get(base+'/steps_tracker/context',timeout=30);assert response.status_code==200
    context=response.json();assert context['role']=='manager' and context['company_id']==company.id
    response=client.get(base+'/steps_tracker/api/configuration',timeout=30);assert response.status_code==200
    config=response.json();assert 'items' in config
    if cerro:assert config['receiver']['supported'] and config['receiver']['online']
    invalid=client.post(base+'/steps_tracker/api/configuration/devices',data={'csrf_token':context['csrf_token'],'method':'POST','payload':json.dumps({'imei':'invalid','brand':'QA','model':'invalid'})},timeout=30)
    assert invalid.status_code==422
    assert client.get(base+'/steps_tracker/api/receiver/poll',timeout=30).status_code==403
    assert client.get(base+'/steps_tracker/api/configuration',timeout=30).json()['items']==config['items']
    os.umask(0o077)
    proof.write_text(json.dumps({'session_id':session.sid,'company_id':company.id,'host':host}))
    proof.chmod(0o600)
    print(json.dumps({'native_review':'OK','database':env.cr.dbname,'menu':'GPS y SIM','action':menu.action.url,'module_version':module.latest_version,'manager_form':True,'invalid_write_rejected':True,'private_receiver_proxy_blocked':True,'registered_devices':len(config['items'])}))
env.cr.rollback()
