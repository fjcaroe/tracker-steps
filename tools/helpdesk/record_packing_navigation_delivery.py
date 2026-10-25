"""Silent T117 QA/T119/T120/T121 delivery with exact destination and package proofs."""
import argparse
import html
import json
from pathlib import Path
import xmlrpc.client


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ticket',type=int,choices=(117,119,120,121))
    parser.add_argument('evidence',type=Path)
    parser.add_argument('--pending-products',action='store_true')
    args=parser.parse_args();root=args.evidence
    assert not args.pending_products or args.ticket==121
    expected=json.loads((root/'delivery-reviewed.json').read_text())[str(args.ticket)]
    targets=('qa-cerro',) if args.ticket==117 else ('development','cerro','qa-cerro')
    for target in targets:
        label=('117-' if args.ticket==117 else '')+target
        proof=json.loads((root/(label+'-qa.json')).read_text())
        log=(root/(label+'-deploy.log')).read_text(encoding='utf-8-sig')
        assert proof['commit']==expected['commit'] and proof['release_sha256']==expected['sha256']
        assert all(marker in log for marker in ('MANAGEMENT_DEPLOY_OK backup=','MANAGEMENT_VERIFY_OK',expected['commit']))
        checks=[json.loads(line.split('MANAGEMENT_REGISTRY_OK ',1)[1]) for line in log.splitlines() if line.startswith('MANAGEMENT_REGISTRY_OK ')]
        if args.ticket in (120,121):
            import re
            qa_log=(root/(target+'-qa.log')).read_text(encoding='utf-8-sig')
            assert '"clone_flow": true' in qa_log
            minimum=33 if args.ticket==121 else 22
            counts=re.findall(r'0 failed, 0 error\(s\) of ([0-9]+) tests',qa_log)
            assert counts and max(map(int,counts))>=minimum
        fields=('native_menu_and_form','two_decimals','native_pallet_weight') if args.ticket==117 else ('native_menu_and_form','native_list','list_first','fruit_selector','operations_order','freights_tab')
        if args.ticket==121: fields=('native_menu_and_form','configured_sources','traceable_transfer')
        if args.ticket==120: fields+=('automatic_tags','simplified_form')
        assert any(item.get('existing_profile',1)!=1 and all(item.get(key) for key in fields)
                   and item.get('writes') is False for item in checks)
    if args.ticket==121:
        original=(root/'development-clone-flow.log').read_text(encoding='utf-8-sig')
        marker=('T121_ORIGINAL_MATERIAL_STOCK_OK pending_product_definition=True' if args.pending_products
                else 'T121_ORIGINAL_OT_REPLAY_OK rollback_required=True')
        assert marker in original
    isolation=(root/'qa-final-isolation.log').read_text(encoding='utf-8-sig')
    assert all(marker in isolation for marker in ('CUSTOMER_QA_VERIFY_OK','CUSTOMER_QA_EGRESS_BLOCKED','CUSTOMER_QA_SOURCE_DB_DENIED'))
    if args.ticket==117:
        body=('Actualizada QA-CERROELPLOMO con el mismo paquete de T117 previamente publicado en Desarrollo y Cerro, '
              'según la respuesta humana 9692. En los maestros están Tara de embalaje y Tara de pallet con dos decimales, '
              'conservando el peso nativo del pallet y los registros anteriores. Dos pruebas aprobadas en copia fresca '
              'de QA, comprobación posterior de origen, versión, menús y formularios con el usuario operativo. '
              'Se conservaron los ejercicios y el aislamiento de QA, sin refrescar datos ni cambiar claves. '
              'Publicado con respaldo y bloqueo. ')
    elif args.ticket==119:
        body=('T119 publicado y verificado en Desarrollo, Cerro y QA-CERROELPLOMO. '
              'Packing / Recepciones / Fruta a proceso abre primero el listado de recepciones a proceso, '
              'incluyendo borradores y registros de otros estados; Nuevo abre el formulario T118. '
              'Se corrigió el orden calculado de las vistas de la acción y se conservaron dominio, contexto, '
              'permisos y registros. Ocho pruebas aprobadas en copias frescas de cada destino; se comprobó '
              'después de publicar versión, origen, menú, listado nativo y formulario con perfiles existentes. '
              'QA conserva sus datos de capacitación y aislamiento. Publicado con respaldo y bloqueo. ')
    elif args.ticket==120:
        body=('T120 publicado y verificado en Desarrollo, Cerro El Plomo y QA-CERROELPLOMO. '
              'La recepción se completa en Encabezado/Operaciones, Fruta con pesaje y distribución por números de tarja, '
              'y Fletes. Al validar se crean y vinculan automáticamente los paquetes nativos tipo C, '
              'con datos de origen, kilos, envases y propietario productor, sin abrir el maestro de paquetes. '
              'Se ocultan el control de envases y la preparación manual en este formulario. '
              'Se separan kilos y cantidad de envases y se conservan movimientos, lotes y entregas parciales. '
              'La recuperación de tarjas validadas prematuramente se limita a las vinculadas a esa recepción, '
              'sin stock ni movimientos históricos ni otra utilización, con origen y detalle coincidentes. '
              'Veintidós pruebas y flujo completo con perfiles existentes aprobados en copias frescas de cada destino; '
              'versión, origen, menú, listado y formulario verificados después de publicar. '
              'Publicación del mismo paquete con respaldo y bloqueo, conservando datos y aislamiento de QA. ')
    else:
        body=('T121 publicado y verificado en Desarrollo, Cerro El Plomo y QA-CERROELPLOMO. '
              'Configurada la bodega nativa Packing y sus ubicaciones de fruta y materiales; se reutilizó la bodega existente en Desarrollo. '
              'El cierre rebaja los materiales desde el origen configurado y muestra la ubicación exacta ante falta de stock. '
              'Validar la OT traslada las tarjas C a Packing con sus paquetes, lotes y propietario; '
              'las OT ya validadas hacen ese traslado al cerrar. El consumo de fruta y la entrada de resultados quedan trazables. '
              'Se respetan reservas, empresa y propiedad de los materiales; un error revierte el cierre completo. '
              'Treinta y tres pruebas por destino y flujo completo con perfiles existentes aprobados en copias frescas; '
              'se reprodujo el cierre de la OT del adjunto exclusivamente en una copia y se revirtió. '
              'Versión, origen, menús, configuración y formulario comprobados después de publicar el mismo paquete con respaldo y bloqueo. '
              'La instalación solo agrega configuración logística; no valida OT reales, inventa existencias ni mueve stock del cliente. '
              'QA conserva sus ejercicios, correo neutralizado, aislamiento y ausencia de acceso a producción. ')
    if args.pending_products:
        findings=json.loads((root/'pending-products.json').read_text())
        body=('T121: corrección de bodega y consumos publicada y verificada en Desarrollo, Cerro El Plomo y QA-CERROELPLOMO. '
              'El origen de materiales es configurable por empresa y separado de la fruta; se reutilizó la bodega Packing existente en Desarrollo. '
              'Las tarjas C se trasladan con su lote y propietario al validar, o al cerrar las OT antiguas. '
              'Treinta y tres pruebas por destino y el flujo completo con perfiles existentes se aprobaron en copias frescas. '
              'Se verificó que los cinco materiales de la OT del adjunto tienen stock suficiente en la ubicación correcta. '
              'La reproducción encontró otro bloqueo, ahora identificado antes de mover paquetes: '
              + findings['summary'] + ' '
              'Se consultó al usuario la definición de unidades y control de inventario. No se modificaron esos productos, '
              'las cantidades, la aprobación ni el estado de la OT real. El ticket permanece abierto hasta recibir la definición '
              'y probar su cierre completo en una copia. Publicado con respaldo y bloqueo, conservando datos y aislamiento de QA. ')
    body+='Commit: '+expected['commit']+'; SHA-256: '+expected['sha256']+'.'
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
    if not args.pending_products:
        call('helpdesk.ticket','write',[[args.ticket],{'stage_id':4}])
    stage=call('helpdesk.ticket','read',[[args.ticket]],{'fields':['stage_id']})[0]['stage_id'][0]
    assert stage==(ticket['stage_id'][0] if args.pending_products else 4)
    for model in ('mail.notification','mail.mail'):
        assert not call(model,'search_count',[[('mail_message_id','=',message)]])
    event='TICKET_PROGRESS_RECORDED' if args.pending_products else 'TICKET_DELIVERY_RECORDED'
    print('%s ticket=%s note=%s stage=%s NO_NOTIFICATIONS_OK'%(event,args.ticket,message,stage))


if __name__=='__main__':main()
