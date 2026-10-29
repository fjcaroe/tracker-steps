"""Record T132-T134 exact-package delivery silently; keep unresolved date choice open."""
import argparse
import html
import json
from pathlib import Path
import re
import xmlrpc.client


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('evidence',type=Path);parser.add_argument('--ticket',type=int,choices=(132,133,134),required=True)
    args=parser.parse_args();root=args.evidence
    expected=json.loads((root/'delivery.json').read_text());expected['reviewed_message_id']=expected['tickets'][str(args.ticket)]
    pending=args.ticket==134 and bool(expected['pending_dates'])
    for target in ('development','cerro','qa-cerro'):
        proof=json.loads((root/(target+'-qa.json')).read_text())
        deployment=json.loads((root/(target+'-deployment.json')).read_text())
        assert proof['commit']==deployment['commit']==expected['commit']
        assert proof['release_sha256']==deployment['sha256']==expected['sha256']
        assert re.search(r'0 failed, 0 error\(s\) of 30 tests',(root/(target+'-qa.log')).read_text(encoding='utf-8-sig'))
        flow=(root/(target+'-clone-flow.log')).read_text(encoding='utf-8-sig')
        assert all(m in flow for m in ('T132_T134_NATIVE_REPORTS_AND_HEADERS_OK','T132_WEIGHT_CORRECTION_PRESERVES_CONTAINERS_OK','T120_OPERATOR_FLOW_OK'))
        live=(root/(target+'-live.log')).read_text(encoding='utf-8-sig')
        assert 'MANAGEMENT_VERIFY_OK' in live and expected['commit'] in live
        payloads=[json.loads(line.split('MANAGEMENT_REGISTRY_OK ',1)[1]) for line in live.splitlines() if line.startswith('MANAGEMENT_REGISTRY_OK ')]
        assert any(p.get('existing_profile',1)!=1 and p.get('native_menu_and_form') and p.get('operations_order') and p.get('writes') is False for p in payloads)
    isolation=(root/'qa-isolation.log').read_text(encoding='utf-8-sig')
    assert all(m in isolation for m in ('CUSTOMER_QA_VERIFY_OK','CUSTOMER_QA_EGRESS_BLOCKED','CUSTOMER_QA_SOURCE_DB_DENIED'))
    migration=json.loads((root/'qa-cerro-live-schema.json').read_text())
    assert len(migration['fields'])==4 and len(migration['views'])==2
    bodies={
        132:'T132: corregido el conteo físico de envases. Ajustar los kilos reales conserva los envases registrados; la prueba de 600 envases y 1.200,50 kg pasó hasta la validación y creación de tarjas nativas. Detalle ordenado, una sola columna de peso neto, totales de bruto/destare/neto y kg por caja con dos decimales y promedio de filas.',
        133:'T133: selector Packing vinculado al contacto existente marcado como Packing. Menú Informes después de Despacho, con stock nativo limitado a las categorías de fruta y materiales de embalajes y sus subcategorías, informes existentes de fruta a proceso/embalada y tarjas con Packing de recepción o proceso. Se reutilizan quants, paquetes y maestros, sin tablas de stock paralelas.',
        134:'T134: encabezado de proceso con Packing y fecha nativa que alimenta Date Packing de las tarjas; compañía debajo del fundo. Al seleccionar productor se propone su primer fundo y se conserva una elección válida del operador. Los prototipos fueron convertidos a campos nativos, conservando IDs y valores y archivando los XML originales.'}
    body=bodies[args.ticket]
    if pending:
        body+=' Queda pendiente la elección humana sobre una fecha discordante del prototipo en QA-Cerro, consultada por este chat. Se conservaron ambos valores y la fecha nativa continúa sin cambios. El ticket permanece En Espera por ese dato; la publicación del formulario no implica resolver la discrepancia.'
    body+=' Mismo paquete publicado y verificado en Desarrollo, Cerro y QA-Cerro después de 30 pruebas por copia, flujo nativo con usuarios existentes, respaldo y bloqueo. Se preservaron cantidades, registros, autores y fechas originales. QA conserva ejercicios y aislamiento. Commit: '+expected['commit']+'; SHA-256: '+expected['sha256']+'.'
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
    call('helpdesk.ticket','write',[[args.ticket],{'stage_id':6 if pending else 4}])
    assert call('helpdesk.ticket','read',[[args.ticket]],{'fields':['stage_id']})[0]['stage_id'][0]==(6 if pending else 4)
    for model in ('mail.notification','mail.mail'):
        assert not call(model,'search_count',[[('mail_message_id','=',message)]])
    assert set(call('mail.message','search',[[('model','=','helpdesk.ticket'),('res_id','=',args.ticket)]]))==original_messages|{message}
    for model,identifiers in original_delivery.items():
        assert set(call(model,'search',[related]))==identifiers, 'Unexpected stage/template notification'
    print('TICKET_DELIVERY_RECORDED ticket=%s note=%s stage=%s NO_NOTIFICATIONS_OK'%(args.ticket,message,6 if pending else 4))


if __name__=='__main__':main()
