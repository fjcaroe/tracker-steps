"""Silent T115/T116 delivery, guarded by destination and isolation proofs."""
import argparse
import html
import json
from pathlib import Path
import xmlrpc.client


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ticket',type=int,choices=(115,116));parser.add_argument('evidence',type=Path)
    args=parser.parse_args();root=args.evidence
    reviewed=json.loads((root/'delivery-reviewed.json').read_text())
    expected=reviewed[str(args.ticket)]
    if args.ticket==116:
        for target in ('development','cerro'):
            proof=json.loads((root/(target+'-qa.json')).read_text())
            log=(root/(target+'-deploy.log')).read_text(encoding='utf-8-sig')
            assert proof['commit']==expected['commit'] and proof['release_sha256']==expected['sha256']
            assert all(marker in log for marker in ('MANAGEMENT_DEPLOY_OK backup=','MANAGEMENT_VERIFY_OK',expected['commit']))
            payloads=[json.loads(line.split('MANAGEMENT_REGISTRY_OK ',1)[1]) for line in log.splitlines() if line.startswith('MANAGEMENT_REGISTRY_OK ')]
            assert any(item.get('ticket')==116 and item.get('existing_profile',1)!=1 and
                       all(item.get(field) for field in ('native_menu_and_form','requested_header','raw_material_first'))
                       and item.get('writes') is False for item in payloads)
        body=('Publicado T116 en Desarrollo y Cerro El Plomo: cabecera de OT reorganizada según el adjunto, '
              'con identificación, especie/variedad, contrato, materia prima e instrucciones en sus posiciones; '
              'Materia Prima es la primera pestaña. Se conservaron campos, relaciones, dominios, permisos, '
              'botones y registros. El mismo paquete pasó dos pruebas en copias frescas de ambos destinos, '
              'preservación de datos y comprobaciones de origen, versión, menú y Form con perfiles existentes. '
              'Publicado con respaldo y bloqueo. La revisión visual por navegador se detuvo por falta de '
              'identificación fiable de la URL; no se declara una comprobación gráfica. Commit: '+expected['commit']+
              '; SHA-256: '+expected['sha256']+'.')
    else:
        creation=json.loads((root/'qa-creation.json').read_text())
        assert creation['database']=='QA-CERROELPLOMO' and creation['source']=='CERRO_EL_PLOMO'
        assert creation['neutralized'] and creation['payroll_accounting_preserved']
        assert creation['source_modules']['step_packing_ot_layout']['version']=='18.0.1.0.0'
        assert 'CUSTOMER_QA_CREATED database=QA-CERROELPLOMO' in (root/'qa-create.log').read_text(encoding='utf-8-sig')
        log=(root/'qa-verify.log').read_text(encoding='utf-8-sig')
        assert all(marker in log for marker in ('CUSTOMER_QA_NATIVE_FLOW_OK','CUSTOMER_QA_EGRESS_BLOCKED','CUSTOMER_QA_VERIFY_OK'))
        assert 'CUSTOMER_QA_HTTPS_OK https://qa-cerroelplomo.stepsapp.cl' in (root/'qa-publish.log').read_text(encoding='utf-8-sig')
        body=('Creada QA-CERROELPLOMO desde una copia consistente de Cerro El Plomo producción, '
              'disponible en https://qa-cerroelplomo.stepsapp.cl para pruebas y capacitación. '
              'Conserva registros y permisos del origen, con base, filestore, código y servicio propios. '
              'La neutralización nativa desactiva integraciones y certificados de la copia; no modifica '
              'credenciales de producción. Correo, tareas programadas y cola saliente están desactivados, '
              'con bloqueo de conexiones salientes IPv4/IPv6 salvo su HTTP local para informes. '
              'Se verificaron HTTPS, formulario y menú nativos con un usuario existente, preservación de '
              'tablas de negocio y bloqueo de salida. Incluye el formulario T116. El pedido T115 y el DNS '
              'confirmado por el usuario documentan esta excepción; no cambia el QA general de Desarrollo, '
              'los destinos de promoción ni la restricción SAG. No hay refrescos automáticos de la copia.')
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
