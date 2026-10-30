"""Record T137 internally without closing an unresolved product definition."""
import argparse
import html
import json
from pathlib import Path
import re
import xmlrpc.client


def main():
    parser=argparse.ArgumentParser();parser.add_argument('evidence',type=Path);args=parser.parse_args()
    root=args.evidence;expected=json.loads((root/'delivery.json').read_text())
    for target in ('development','cerro','qa-cerro'):
        qa=json.loads((root/(target+'-qa.json')).read_text())
        deployment=json.loads((root/(target+'-deployment.json')).read_text())
        assert qa['commit']==deployment['commit']==expected['commit']
        assert qa['release_sha256']==deployment['sha256']==expected['sha256']
        assert re.search(r'0 failed, 0 error\(s\) of [1-9][0-9]* tests', (root/(target+'-qa.log')).read_text(encoding='utf-8-sig'))
        assert 'T137_PREVALIDATED_OUTPUT_NATIVE_CLOSE_OK no_duplicate_stock=True' in (root/(target+'-flow.log')).read_text(encoding='utf-8-sig')
        live=(root/(target+'-live.log')).read_text(encoding='utf-8-sig')
        payloads=[json.loads(line.split('MANAGEMENT_REGISTRY_OK ',1)[1]) for line in live.splitlines() if line.startswith('MANAGEMENT_REGISTRY_OK ')]
        assert 'MANAGEMENT_VERIFY_OK' in live and expected['commit'] in live
        assert any(p.get('existing_profile',1)!=1 and p.get('native_menu_and_form') and p.get('writes') is False for p in payloads)
    assert all(m in (root/'isolation.log').read_text() for m in ('CUSTOMER_QA_VERIFY_OK','CUSTOMER_QA_EGRESS_BLOCKED','CUSTOMER_QA_SOURCE_DB_DENIED'))
    assert 'T137_REPORTED_QUADRATURE_OK' in (root/'qa-cerro-flow.log').read_text(encoding='utf-8-sig')
    pending=expected['pending_product_inventory'];stage=6 if pending else 4
    body=('T137: corregida la validación de cuadratura para tarjas E/N ya validadas de su propia OT, '
        'sin existencias ni historial de movimientos. Se conserva su validación y se impide producir stock por duplicado. '
        'También comprobado el cierre nativo con tarjas previamente validadas. Publicado el mismo paquete en Desarrollo, '
        'Cerro y QA-Cerro tras pruebas en copias frescas, menú/formulario y flujo con usuarios existentes, preservación '
        'de datos, respaldo y bloqueo compartido. No se validó ni cerró la OT real durante la publicación. ')
    if pending:
        body+=('El caso real pasa el control de tarjas en copia, pero el control nativo de inventario detecta un producto '
            'de exportación configurado sin controlar stock. Su definición se consultó al usuario en este chat; '
            'no se cambió sin confirmación. El ticket permanece En Espera por ese dato. ')
    body+='Pruebas aprobadas: '+str(expected['tests'])+'. Commit: '+expected['commit']+'; SHA-256: '+expected['sha256']+'.'
    c=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'));url='https://soporte.stepsapp.cl'
    uid=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(c['db'],c['username'],c['api_key'],{});assert uid
    rpc=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object');context={'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,'mail_notify_force_send':False,'mail_auto_subscribe_no_notify':True}
    def call(model,method,values,kw=None):return rpc.execute_kw(c['db'],uid,c['api_key'],model,method,values,dict({'context':context},**(kw or {})))
    ticket=call('helpdesk.ticket','read',[[137]],{'fields':['stage_id','sla_ids','sla_status_ids']})[0]
    assert ticket['stage_id'][0] not in (4,5) and not ticket['sla_ids'] and not ticket['sla_status_ids']
    model=call('ir.model','search',[[('model','=','helpdesk.ticket')]])
    assert not call('base.automation','search_count',[[('model_id','in',model),('active','=',True)]])
    assert not call('mail.message','search_count',[[('model','=','helpdesk.ticket'),('res_id','=',137),('id','>',expected['reviewed_message_id']),('message_type','in',['comment','email'])]])
    author=call('res.users','read',[[uid]],{'fields':['partner_id']})[0]['partner_id'][0]
    subtype=call('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
    domain=[('mail_message_id.model','=','helpdesk.ticket'),('mail_message_id.res_id','=',137)]
    deliveries={m:set(call(m,'search',[domain])) for m in ('mail.notification','mail.mail')}
    message=call('mail.message','create',[{'model':'helpdesk.ticket','res_id':137,'message_type':'comment','subtype_id':subtype,'author_id':author,'partner_ids':[(6,0,[])],'body':'<p>'+html.escape(body)+'</p>'}])
    call('helpdesk.ticket','write',[[137],{'stage_id':stage}])
    assert call('helpdesk.ticket','read',[[137]],{'fields':['stage_id']})[0]['stage_id'][0]==stage
    for model,ids in deliveries.items():assert set(call(model,'search',[domain]))==ids
    print('T137_DELIVERY_RECORDED note=%s stage=%s NO_NOTIFICATIONS_OK'%(message,stage))


if __name__=='__main__':main()
