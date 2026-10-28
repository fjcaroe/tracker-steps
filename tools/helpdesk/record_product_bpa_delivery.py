"""Silent T127 delivery after Community and three destination evidence checks."""
import argparse
import html
import json
from pathlib import Path
import re
import xmlrpc.client


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence',type=Path)
    args=parser.parse_args();args.ticket=127;root=args.evidence
    expected=json.loads((root/'delivery-reviewed.json').read_text())['127']
    community=json.loads((root/'community.json').read_text())
    assert community['community_only'] and community['tests_passed']
    assert 'step_product_bpa' in community['installed']
    assert all(license not in ('OEEL-1','OPL-1') for license in community['licenses'].values())
    for target in ('development','cerro','qa-cerro'):
        proof=json.loads((root/(target+'-qa.json')).read_text())
        qa=(root/(target+'-qa.log')).read_text(encoding='utf-8-sig')
        flow=(root/(target+'-clone-flow.log')).read_text(encoding='utf-8-sig')
        live=(root/(target+'-live.log')).read_text(encoding='utf-8-sig')
        deployment=json.loads((root/(target+'-deployment.json')).read_text())
        assert proof['commit']==deployment['commit']==expected['commit']
        assert proof['release_sha256']==deployment['sha256']==expected['sha256']
        assert Path(deployment['overlay']).name==expected['commit']
        assert re.search(r'0 failed, 0 error\(s\) of 3 tests',qa)
        assert 'T127_OPERATOR_NATIVE_FORM_FLOW_OK' in flow and 'rollback_required=True' in flow
        assert 'MANAGEMENT_VERIFY_OK' in live and expected['commit'] in live
        payloads=[json.loads(line.split('MANAGEMENT_REGISTRY_OK ',1)[1]) for line in live.splitlines() if line.startswith('MANAGEMENT_REGISTRY_OK ')]
        assert any(p.get('existing_profile',1)!=1 and p.get('native_menu_form') and p.get('writes') is False for p in payloads)
    isolation=(root/'qa-final-isolation.log').read_text(encoding='utf-8-sig')
    assert all(m in isolation for m in ('CUSTOMER_QA_VERIFY_OK','CUSTOMER_QA_EGRESS_BLOCKED','CUSTOMER_QA_SOURCE_DB_DENIED'))
    body=('T127: implementados como código propio siete campos de registro BPA y el maestro de aptitudes plaguicidas. '
        'El núcleo se probó en una base nueva con addons de licencia abierta, sin Studio ni Enterprise. '
        'Se reutilizan sustancia activa y carencias nativas. La conversión conserva IDs, relaciones, textos, fechas, permisos e historial; '
        'no copia clasificaciones de otra empresa ni cambia los datos sanitarios de los productos. '
        'Publicado y verificado en Desarrollo, Cerro El Plomo y QA-CERROELPLOMO. '
        'Pruebas funcionales y flujo de formulario con perfiles existentes aprobados en copias frescas. '
        'Mismo paquete probado, respaldo y bloqueo; QA conserva sus datos y aislamiento. '
        'Commit: '+expected['commit']+'; SHA-256: '+expected['sha256']+'.')
    c=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
    url='https://soporte.stepsapp.cl'
    uid=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(c['db'],c['username'],c['api_key'],{})
    assert uid;rpc=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object')
    context={'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,
             'mail_notify_force_send':False,'mail_auto_subscribe_no_notify':True}
    def call(model,method,values,kwargs=None):
        return rpc.execute_kw(c['db'],uid,c['api_key'],model,method,values,dict({'context':context},**(kwargs or {})))
    ticket=call('helpdesk.ticket','read',[[args.ticket]],{'fields':['stage_id','sla_ids','sla_status_ids']})[0]
    assert ticket['stage_id'][0] not in (4,5) and not ticket['sla_ids'] and not ticket['sla_status_ids']
    model=call('ir.model','search',[[('model','=','helpdesk.ticket')]])
    assert not call('base.automation','search_count',[[('model_id','in',model),('active','=',True)]])
    assert not call('mail.message','search_count',[[('model','=','helpdesk.ticket'),('res_id','=',args.ticket),
        ('id','>',expected['reviewed_message_id']),('message_type','in',['comment','email'])]])
    author=call('res.users','read',[[uid]],{'fields':['partner_id']})[0]['partner_id'][0]
    subtype=call('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
    related=[('mail_message_id.model','=','helpdesk.ticket'),('mail_message_id.res_id','=',args.ticket)]
    original_messages=set(call('mail.message','search',[[('model','=','helpdesk.ticket'),('res_id','=',args.ticket)]]))
    original_delivery={m:set(call(m,'search',[related])) for m in ('mail.notification','mail.mail')}
    message=call('mail.message','create',[{'model':'helpdesk.ticket','res_id':args.ticket,'message_type':'comment',
        'subtype_id':subtype,'author_id':author,'partner_ids':[(6,0,[])],'body':'<p>'+html.escape(body)+'</p>'}])
    call('helpdesk.ticket','write',[[args.ticket],{'stage_id':4}])
    assert call('helpdesk.ticket','read',[[args.ticket]],{'fields':['stage_id']})[0]['stage_id'][0]==4
    for model in ('mail.notification','mail.mail'):
        assert not call(model,'search_count',[[('mail_message_id','=',message)]])
    assert set(call('mail.message','search',[[('model','=','helpdesk.ticket'),('res_id','=',args.ticket)]]))==original_messages|{message}
    for model,identifiers in original_delivery.items():
        assert set(call(model,'search',[related]))==identifiers, 'Unexpected stage/template notification'
    print('TICKET_DELIVERY_RECORDED ticket=%s note=%s stage=4 NO_NOTIFICATIONS_OK'%(args.ticket,message))


if __name__=='__main__':main()
