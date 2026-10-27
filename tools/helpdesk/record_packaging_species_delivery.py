"""Silent T124/T125/T126 closure gated on all three destination deliveries."""
import argparse
import html
import json
from pathlib import Path
import re
import xmlrpc.client


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ticket',type=int,choices=(124,125,126))
    parser.add_argument('evidence',type=Path)
    args=parser.parse_args();root=args.evidence
    expected=json.loads((root/'delivery-reviewed.json').read_text())[str(args.ticket)]
    minimum=2 if args.ticket==126 else 5
    marker='T126_OPERATOR_NATIVE_FORM_FLOW_OK' if args.ticket==126 else 'T124_T125_OPERATOR_FLOW_OK'
    for target in ('development','cerro','qa-cerro'):
        proof=json.loads((root/(target+'-qa.json')).read_text())
        qa=(root/(target+'-qa.log')).read_text(encoding='utf-8-sig')
        flow=(root/(target+'-clone-flow.log')).read_text(encoding='utf-8-sig')
        live=(root/(target+'-live.log')).read_text(encoding='utf-8-sig')
        deployment=json.loads((root/(target+'-deployment.json')).read_text())
        assert proof['commit']==deployment['commit']==expected['commit']
        assert proof['release_sha256']==deployment['sha256']==expected['sha256']
        assert Path(deployment['overlay']).name==expected['commit']
        counts=re.findall(r'0 failed, 0 error\(s\) of ([0-9]+) tests',qa)
        assert counts and max(map(int,counts))>=minimum
        assert marker in flow and 'rollback_required=True' in flow
        if args.ticket in (124,125):
            hierarchy=(root/(target+'-hierarchy.log')).read_text(encoding='utf-8-sig')
            receipts=[json.loads(line.split('T125_HIERARCHY_CONFIGURED ',1)[1]) for line in hierarchy.splitlines() if line.startswith('T125_HIERARCHY_CONFIGURED ')]
            assert receipts and receipts[-1]['accounts_preserved'] and receipts[-1]['category_ids_preserved']
            if target=='cerro':
                assert len(receipts[-1]['children'])==2 and receipts[-1]['products_preserved']>0
            if target=='qa-cerro':
                assert (len(receipts[-1]['children'])==2 and receipts[-1]['products_preserved']>0) or (receipts[-1].get('children_absent') and receipts[-1]['changed']==0)
        assert 'MANAGEMENT_VERIFY_OK' in live and expected['commit'] in live
        payloads=[json.loads(line.split('MANAGEMENT_REGISTRY_OK ',1)[1]) for line in live.splitlines() if line.startswith('MANAGEMENT_REGISTRY_OK ')]
        assert any(p.get('existing_profile',1)!=1 and p.get('native_menu_and_form') and p.get('writes') is False for p in payloads)
    isolation=(root/'qa-final-isolation.log').read_text(encoding='utf-8-sig')
    assert all(m in isolation for m in ('CUSTOMER_QA_VERIFY_OK','CUSTOMER_QA_EGRESS_BLOCKED','CUSTOMER_QA_SOURCE_DB_DENIED'))
    bodies={
        124:'Agregados al embalaje existente cantidad y peso de clamshell en gramos, cajas por pallet, pallets por contenedor, cajas por contenedor de 40 y peso neto por pallet. Los dos últimos se calculan con las fórmulas del adjunto y los kg por caja existentes; no se reemplazaron cantidad incluida ni tara. ',
        125:'Corregida la selección de componentes de listas de materiales: reconoce las categorías existentes sin distinguir mayúsculas y minúsculas, incluye sus subcategorías y conserva el rechazo de maestros ambiguos. No se renombraron categorías ni reclasificaron productos. Agregado Packing / Maestros / Listas de materiales de fruta reutilizando la acción y registros originales. ',
        126:'Agregado Código arancelario como texto opcional en el maestro original de especies, en formulario y lista. Conserva ceros iniciales y caracteres de texto. No se precargaron códigos ni se duplicaron especies. '}
    body=bodies[args.ticket]+('Publicado y verificado en Desarrollo, Cerro El Plomo y QA-CERROELPLOMO. '
        'Pruebas funcionales y flujo de usuario existente en copias frescas; versión, origen, menú y formulario comprobados tras publicar el mismo paquete con respaldo y bloqueo. '
        'Datos, permisos y aislamiento de QA conservados. Commit: '+expected['commit']+'; SHA-256: '+expected['sha256']+'.')
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
