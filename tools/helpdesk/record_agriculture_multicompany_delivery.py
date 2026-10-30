"""Record T139/T140 deliveries silently after exact-package functional proof."""
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
        live=(root/(target+'-live.log')).read_text(encoding='utf-8-sig')
        payloads=[json.loads(line.split('MANAGEMENT_REGISTRY_OK ',1)[1]) for line in live.splitlines() if line.startswith('MANAGEMENT_REGISTRY_OK ')]
        assert 'MANAGEMENT_VERIFY_OK' in live and expected['commit'] in live
        assert any(p.get('existing_profile',1)!=1 and p.get('native_menu_and_form') and p.get('writes') is False for p in payloads)
    assert all(m in (root/'isolation.log').read_text() for m in ('CUSTOMER_QA_VERIFY_OK','CUSTOMER_QA_EGRESS_BLOCKED','CUSTOMER_QA_SOURCE_DB_DENIED'))
    pair=json.loads((root/'pair.json').read_text())
    assert pair['cerro']['step_agriculture_multicompany']['version']==pair['qa-cerro']['step_agriculture_multicompany']['version']=='18.0.1.0.0'
    assert pair['cerro']['step_agriculture_multicompany']['sha256']==pair['qa-cerro']['step_agriculture_multicompany']['sha256']
    body=('T139/T140: los maestros de Fundos de productores, categoría, clase, calidad y color de fruta permiten '
          'seleccionar varias empresas y sucursales. Fundos está disponible también en Packing / Maestros. '
          'Los registros, IDs, relaciones y empresa original se conservaron. Cada registro mantiene su empresa '
          'original y permite agregar otras explícitamente; no se comparten automáticamente con todas las empresas. '
          'Se verificaron permisos, formularios, consistencia en operaciones y controles de asignación, códigos '
          'duplicados y retiro de empresas usadas. Documentos contables e inventario permanecen separados. '
          'Publicado el mismo paquete en Desarrollo, Cerro y QA-Cerro, con pruebas en copias frescas, usuarios '
          'existentes, respaldo y bloqueo. QA conserva capacitación y aislamiento. Versión y código efectivo '
          'iguales en ambos Cerro. Pruebas aprobadas: '+str(expected['tests'])+'. Commit: '+expected['commit']+
          '; SHA-256: '+expected['sha256']+'.')
    c=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'));url='https://soporte.stepsapp.cl'
    uid=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(c['db'],c['username'],c['api_key'],{});assert uid
    rpc=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object');context={'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,'mail_notify_force_send':False,'mail_auto_subscribe_no_notify':True}
    def call(model,method,values,kw=None):return rpc.execute_kw(c['db'],uid,c['api_key'],model,method,values,dict({'context':context},**(kw or {})))
    for tid in (139,140):
        ticket=call('helpdesk.ticket','read',[[tid]],{'fields':['stage_id','sla_ids','sla_status_ids']})[0]
        assert ticket['stage_id'][0] not in (4,5) and not ticket['sla_ids'] and not ticket['sla_status_ids']
        assert not call('mail.message','search_count',[[('model','=','helpdesk.ticket'),('res_id','=',tid),('id','>',expected['reviewed_messages'][str(tid)]),('message_type','in',['comment','email'])]])
    model=call('ir.model','search',[[('model','=','helpdesk.ticket')]])
    assert not call('base.automation','search_count',[[('model_id','in',model),('active','=',True)]])
    author=call('res.users','read',[[uid]],{'fields':['partner_id']})[0]['partner_id'][0]
    subtype=call('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
    for tid in (139,140):
        domain=[('mail_message_id.model','=','helpdesk.ticket'),('mail_message_id.res_id','=',tid)]
        deliveries={m:set(call(m,'search',[domain])) for m in ('mail.notification','mail.mail')}
        message=call('mail.message','create',[{'model':'helpdesk.ticket','res_id':tid,'message_type':'comment','subtype_id':subtype,'author_id':author,'partner_ids':[(6,0,[])],'body':'<p>'+html.escape(body)+'</p>'}])
        call('helpdesk.ticket','write',[[tid],{'stage_id':4}])
        assert call('helpdesk.ticket','read',[[tid]],{'fields':['stage_id']})[0]['stage_id'][0]==4
        for model,ids in deliveries.items():assert set(call(model,'search',[domain]))==ids
        print('T%s_DELIVERY_RECORDED note=%s stage=4 NO_NOTIFICATIONS_OK'%(tid,message))


if __name__=='__main__':main()
