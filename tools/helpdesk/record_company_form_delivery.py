"""Silent T130 delivery after all three company-form destinations are verified."""
import argparse
import html
import json
from pathlib import Path
import re
import xmlrpc.client


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence',type=Path)
    args=parser.parse_args();args.ticket=130;root=args.evidence
    expected=json.loads((root/'delivery-reviewed.json').read_text())['130']
    for target in ('development','cerro','qa-cerro'):
        proof=json.loads((root/(target+'-qa.json')).read_text())
        qa=(root/(target+'-qa.log')).read_text(encoding='utf-8-sig')
        flow=(root/(target+'-clone-flow.log')).read_text(encoding='utf-8-sig')
        live=(root/(target+'-live.log')).read_text(encoding='utf-8-sig')
        deployment=json.loads((root/(target+'-deployment.json')).read_text())
        assert proof['commit']==deployment['commit']==expected['commit']
        assert proof['release_sha256']==deployment['sha256']==expected['sha256']
        assert Path(deployment['overlay']).name==expected['commit']
        assert re.search(r'0 failed, 0 error\(s\) of 11 tests',qa)
        assert 'T130_NATIVE_COMPANY_FORM_FLOW_OK' in flow and 'rollback_required=True' in flow
        assert 'MANAGEMENT_VERIFY_OK' in live and expected['commit'] in live
        payloads=[json.loads(line.split('MANAGEMENT_REGISTRY_OK ',1)[1]) for line in live.splitlines() if line.startswith('MANAGEMENT_REGISTRY_OK ')]
        assert any(p.get('existing_profile',1)!=1 and p.get('native_menu_and_form') and p.get('compact_actions_preserved') and 'steps_previred' in p.get('complete_pages',[]) and p.get('writes') is False for p in payloads)
    isolation=(root/'qa-isolation.log').read_text(encoding='utf-8-sig')
    assert all(m in isolation for m in ('CUSTOMER_QA_VERIFY_OK','CUSTOMER_QA_EGRESS_BLOCKED','CUSTOMER_QA_SOURCE_DB_DENIED'))
    body=('T130: restablecido el formulario y listado completos de Ajustes / Empresas. '
        'El formulario nativo conserva sus pestañas heredadas y los controles de identidad, moneda, sucursales, nómina y DTE. '
        'Folios y Bodega Packing mantienen sus vistas específicas. La pestaña Previred obsoleta de Studio se conserva archivada '
        'y se reemplaza por una vista en código que usa los parámetros nativos existentes, sin modificar valores ni cálculos. '
        'Publicado y verificado en Desarrollo, Cerro El Plomo y QA-CERROELPLOMO con el mismo paquete probado en copias frescas, respaldo y bloqueo. '
        'Once pruebas por copia y flujo nativo con perfiles existentes aprobados. Datos y permisos preservados; QA conserva su aislamiento. '
        'Según respuesta del usuario, la configuración DTE puede quedar pendiente sin impedir guardar la empresa: se muestra aviso con los datos faltantes. Se conservan las validaciones nativas al procesar DTE y se comprueba la resolución antes de generar documentos; no se inventaron correos ni resoluciones. '
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
