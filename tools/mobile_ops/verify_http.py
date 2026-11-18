"""Verify live Desarrollo onboarding with one synthetic, finally suspended account.

No email, employee links, business operations or existing credential changes.
The synthetic audit trail is preserved, not deleted.
"""
import argparse
import json
import secrets
import urllib.request
import uuid
import xmlrpc.client
from pathlib import Path

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--credentials', type=Path, required=True)
    p.add_argument('--company', type=int, required=True)
    p.add_argument('--cleanup', action='store_true', help='Revoke memberships of suspended synthetic HTTP checks')
    a = p.parse_args(); c = json.loads(a.credentials.read_text())
    assert c['url'].rstrip('/') == 'https://desarrollo.stepsapp.cl' and c['db'] == 'LAB_TAREAS'
    uid = xmlrpc.client.ServerProxy(c['url']+'/xmlrpc/2/common').authenticate(c['db'],c['username'],c['api_key'],{})
    assert uid
    def call(model, method, args, **kwargs):
        payload = {'jsonrpc':'2.0','method':'call','id':1,'params':{'service':'object','method':'execute_kw',
            'args':[c['db'],uid,c['api_key'],model,method,args,kwargs]}}
        req = urllib.request.Request(c['url']+'/jsonrpc',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=30) as response: result = json.load(response)
        assert 'error' not in result, 'Odoo rejected '+model+'.'+method
        return result.get('result')  # Odoo omits the key for void model actions.
    assert call('ir.config_parameter','get_param',['step_app.send_mail','0']) != '1', 'Outgoing mail must be disabled for this test'
    if a.cleanup:
        people = call('step.app.person','search_read',[[['name','=','QA Android HTTP (ficticio)'],['state','=','suspended']]],fields=['email'])
        for person in people:
            assert person['email'].startswith('qa-android-') and person['email'].endswith('@example.invalid')
            memberships = call('step.app.membership','search',[[['person_id','=',person['id']],['company_id','=',a.company],['state','!=','revoked']]])
            if memberships: call('step.app.membership','action_revoke',[memberships])
        print('SYNTHETIC_MEMBERSHIPS_REVOKED_AUDIT_PRESERVED',len(people))
        return
    company = call('res.company','read',[[a.company]],fields=['step_app_org_code','step_app_org_uid'])[0]
    token = None; person_id = None
    def request(method,path,body=None,org=False):
        headers = {'Content-Type':'application/json'}
        if token: headers['Authorization'] = 'Bearer '+token
        if org: headers['X-Steps-Org'] = company['step_app_org_uid']
        req = urllib.request.Request(c['url']+'/steps_app/v1'+path,
            data=None if body is None else json.dumps(body).encode(),headers=headers,method=method)
        with urllib.request.urlopen(req,timeout=30) as response: return json.load(response)
    email = 'qa-android-'+uuid.uuid4().hex+'@example.invalid'
    try:
        pair = request('POST','/auth/register',{'email':email,'password':secrets.token_urlsafe(32),
            'name':'QA Android HTTP (ficticio)','device':{'uuid':str(uuid.uuid4()),'platform':'qa-http','label':'QA temporal'}})
        token = pair['access_token']
        me = request('GET','/me'); person_id = me['person']['id']
        assert me['onboarding'] == 'no_organization'
        assert request('POST','/access/request',{'org_code':company['step_app_org_code'],'note':'QA Android: solicitud ficticia'})['state'] == 'requested'
        memberships = call('step.app.membership','search',[[['person_id','=',person_id],['company_id','=',a.company]]])
        assert len(memberships) == 1
        call('step.app.membership','action_approve',[memberships])
        role = call('ir.model.data','search_read',[[['module','=','step_mobile_portal_colaciones'],['name','=','step_app_role_colaciones_persona']]],fields=['res_id'])[0]['res_id']
        role_data = call('step.app.module.role','read',[[role]],fields=['module_id'])[0]
        call('step.app.grant','create',[{'membership_id':memberships[0],'module_id':role_data['module_id'][0],'role_id':role}])
        catalog = request('GET','/catalog?supported=colaciones:1',org=True)
        assert [m['code'] for m in catalog['modules']] == ['colaciones']
        own = request('GET','/colaciones/me',org=True)
        assert own['linked'] is False
        print('DESARROLLO_HTTP_REGISTRATION_REQUEST_APPROVAL_CATALOG_OWN_SCOPE_OK')
    finally:
        if person_id:
            memberships = call('step.app.membership','search',[[['person_id','=',person_id],['company_id','=',a.company]]])
            if memberships: call('step.app.membership','action_revoke',[memberships])
            call('step.app.person','action_suspend',[[person_id]])
            assert call('step.app.person','read',[[person_id]],fields=['state'])[0]['state'] == 'suspended'
            print('SYNTHETIC_ACCOUNT_SUSPENDED_AUDIT_PRESERVED')

if __name__ == '__main__': main()
