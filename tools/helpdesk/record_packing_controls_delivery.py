"""Record silent T114/T121/T122 delivery only after all destination proofs pass."""
import argparse
import html
import json
from pathlib import Path
import re
import xmlrpc.client


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ticket',type=int,choices=(114,121,122))
    parser.add_argument('evidence',type=Path)
    args=parser.parse_args();root=args.evidence
    expected=json.loads((root/'delivery-reviewed.json').read_text())[str(args.ticket)]
    for target in ('development','cerro','qa-cerro'):
        proof=json.loads((root/(target+'-qa.json')).read_text())
        qa=(root/(target+'-qa.log')).read_text(encoding='utf-8-sig')
        flow=(root/(target+'-clone-flow.log')).read_text(encoding='utf-8-sig')
        deploy=(root/(target+'-deploy.log')).read_text(encoding='utf-8-sig')
        assert proof['commit']==expected['commit'] and proof['release_sha256']==expected['sha256']
        counts=re.findall(r'0 failed, 0 error\(s\) of ([0-9]+) tests',qa)
        assert counts and max(map(int,counts))>=23
        assert 'T114_T122_OPERATOR_ACCOUNTING_FLOW_OK' in flow
        assert all(marker in deploy for marker in ('MANAGEMENT_DEPLOY_OK backup=','MANAGEMENT_VERIFY_OK',expected['commit']))
        payloads=[json.loads(line.split('MANAGEMENT_REGISTRY_OK ',1)[1]) for line in deploy.splitlines() if line.startswith('MANAGEMENT_REGISTRY_OK ')]
        assert any(item.get('existing_profile',1)!=1 and item.get('native_menu_and_form') and item.get('analytic_rules')
                   and item.get('profile_groups')==9 and item.get('writes') is False for item in payloads)
    development=(root/'development-clone-flow.log').read_text(encoding='utf-8-sig')
    assert 'T122_ORIGINAL_DRAFT_RECLASSIFICATION_OK' in development
    assert 'T121_CONFIRMED_CYCLE_OK writes=False' in (root/'development-live-flow.log').read_text(encoding='utf-8-sig')
    isolation=(root/'qa-final-isolation.log').read_text(encoding='utf-8-sig')
    assert all(marker in isolation for marker in ('CUSTOMER_QA_VERIFY_OK','CUSTOMER_QA_EGRESS_BLOCKED','CUSTOMER_QA_SOURCE_DB_DENIED'))
    bodies={
        114:('Publicados perfiles de Consulta, Operación y Administración por aplicación para Packing, Exportaciones y Productores. '
             'Se seleccionan en el formulario nativo de Usuarios. Consulta permite leer; Operación trabajar documentos y sus líneas; '
             'Administración agrega mantenimiento y eliminación. Los controles se aplican también por API y ocultan las otras aplicaciones. '
             'Son perfiles opcionales: no se reasignó ningún usuario y se conservan los permisos existentes de quienes aún no los tienen. '
             'No otorgan administración del sistema ni de Contabilidad; la aprobación contable conserva sus permisos nativos. '),
        121:('Revisada la respuesta 9720: se respeta la definición de unidades del usuario. '
             'Se comprobó que la OT del adjunto está cerrada y sus traslados, consumos y entrada de resultados están completados, '
             'con materiales y fruta desde las ubicaciones configuradas. No se cambiaron productos, unidades, cantidades ni la OT real. '
             'Se verificó además el ciclo completo en copias de los tres destinos. '),
        122:('Publicado el control contable de consumos de Packing. El débito toma la cuenta de gasto del producto o su categoría '
             'y el crédito conserva la cuenta de inventario. En Packing / Configuraciones / Packing / Planes analíticos se habilitaron '
             'Temporada desde la OT, Centro de costos desde la especie y OT Packing desde su número; los demás planes quedan sin aplicar. '
             'La cuenta analítica de OT se crea al preparar el comprobante y se reutiliza. Las devoluciones revierten la cuenta y analítica del consumo. '
             'La pestaña Contabilización y analítica permite revisar comprobantes anteriores: genera reclasificaciones en borrador '
             'cuando corresponde, sin cambiar importes o cuentas de asientos ya contabilizados. Su publicación requiere revisión contable. ')}
    body=bodies[args.ticket]+('Disponible y verificado en Desarrollo, Cerro El Plomo y QA-CERROELPLOMO. '
        'Veintitrés pruebas por destino y flujo funcional de operación/contabilidad en copias frescas; '
        'origen, versión, menú y formularios comprobados después de publicar el mismo paquete con respaldo y bloqueo. '
        'Se conservaron datos, usuarios y aislamiento de QA. Commit: '+expected['commit']+'; SHA-256: '+expected['sha256']+'.')
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
    message=call('mail.message','create',[{'model':'helpdesk.ticket','res_id':args.ticket,'message_type':'comment',
        'subtype_id':subtype,'author_id':author,'partner_ids':[(6,0,[])],'body':'<p>'+html.escape(body)+'</p>'}])
    call('helpdesk.ticket','write',[[args.ticket],{'stage_id':4}])
    assert call('helpdesk.ticket','read',[[args.ticket]],{'fields':['stage_id']})[0]['stage_id'][0]==4
    for model in ('mail.notification','mail.mail'):
        assert not call(model,'search_count',[[('mail_message_id','=',message)]])
    print('TICKET_DELIVERY_RECORDED ticket=%s note=%s stage=4 NO_NOTIFICATIONS_OK'%(args.ticket,message))


if __name__=='__main__':main()
