"""Record T118 internally only after immutable-package functional delivery."""
import argparse
import html
import json
from pathlib import Path
import xmlrpc.client


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence',type=Path)
    args=parser.parse_args();root=args.evidence
    args.ticket=118
    expected=json.loads((root/'delivery-reviewed.json').read_text())['118']
    for target in ('development','cerro','qa-cerro'):
        proof=json.loads((root/(target+'-qa.json')).read_text())
        log=(root/(target+'-deploy.log')).read_text(encoding='utf-8-sig')
        assert proof['commit']==expected['commit'] and proof['release_sha256']==expected['sha256']
        assert all(marker in log for marker in ('MANAGEMENT_DEPLOY_OK backup=','MANAGEMENT_VERIFY_OK',expected['commit']))
        checks=[json.loads(line.split('MANAGEMENT_REGISTRY_OK ',1)[1]) for line in log.splitlines() if line.startswith('MANAGEMENT_REGISTRY_OK ')]
        assert any(item.get('ticket')==118 and item.get('existing_profile',1)!=1
                   and all(item.get(key) for key in ('native_menu_and_form','operations_order','freights_tab','master_class','contract_scope','fruit_selector'))
                   and item.get('writes') is False for item in checks)
    isolation=(root/'qa-final-isolation.log').read_text(encoding='utf-8-sig')
    assert all(marker in isolation for marker in ('CUSTOMER_QA_NATIVE_FLOW_OK','CUSTOMER_QA_EGRESS_BLOCKED','CUSTOMER_QA_SOURCE_DB_DENIED','CUSTOMER_QA_VERIFY_OK'))
    assert 'CUSTOMER_QA_CLONE_ACCESS_REMOVED' in (root/'qa-cerro-final-qa.log').read_text(encoding='utf-8-sig')
    body=('T118 publicado y verificado en Desarrollo, Cerro El Plomo y QA-CERROELPLOMO. '
          'Recepción de fruta a proceso incorpora contrato vigente del productor, tipo y cantidad de pallet, '
          'cantidad de envases y columnas en el orden solicitado. Flete pasa a la pestaña Fletes; '
          'Clase de fruta refiere el maestro existente y se retiran del formulario los textos duplicados '
          'de pesaje y contrato. Fecha guía queda debajo del número de guía. '
          'Según la respuesta del usuario en este chat, Tipo de fruta usa Convencional/Orgánica. '
          'Los textos históricos se conservan y las clasificaciones sin equivalencia quedan visibles para revisión. '
          'El mismo paquete pasó siete pruebas en copias frescas de los tres destinos; se verificaron versión, '
          'origen, menú y formulario con perfiles existentes después de publicar. '
          'QA conserva sus ejercicios, correo desactivado, aislamiento de red y bloqueo de acceso a producción. '
          'Publicación con respaldo y bloqueo compartido. No se guardaron pruebas en las bases vivas. '
          'Commit: '+expected['commit']+'; SHA-256: '+expected['sha256']+'.')
    c=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
    url='https://soporte.stepsapp.cl';uid=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(c['db'],c['username'],c['api_key'],{})
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
    message=call('mail.message','create',[{'model':'helpdesk.ticket','res_id':args.ticket,'message_type':'comment',
        'subtype_id':subtype,'author_id':author,'partner_ids':[(6,0,[])],'body':'<p>'+html.escape(body)+'</p>'}])
    call('helpdesk.ticket','write',[[args.ticket],{'stage_id':4}])
    assert call('helpdesk.ticket','read',[[args.ticket]],{'fields':['stage_id']})[0]['stage_id'][0]==4
    for model in ('mail.notification','mail.mail'):
        assert not call(model,'search_count',[[('mail_message_id','=',message)]])
    print('TICKET_DELIVERY_RECORDED ticket=%s note=%s stage=4 NO_NOTIFICATIONS_OK'%(args.ticket,message))


if __name__=='__main__':main()
