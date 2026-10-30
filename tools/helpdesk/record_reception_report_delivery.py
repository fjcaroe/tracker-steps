"""Record T141 deliveries silently after exact-package functional proof."""
import argparse
import html
import hashlib
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
    assert pair['cerro']['step_packing_reception_report']['version']==pair['qa-cerro']['step_packing_reception_report']['version']=='18.0.1.0.1'
    assert pair['cerro']['step_packing_reception_report']['sha256']==pair['qa-cerro']['step_packing_reception_report']['sha256']
    for target in ('development','cerro','qa-cerro'):
        review=json.loads((root/(target+'-visual-review.json')).read_text(encoding='utf-8-sig'))
        assert review['reviewed'] is True
        for name,item in review['files'].items():
            assert hashlib.sha256((root/(target+'-'+name)).read_bytes()).hexdigest()==item['sha256']
    assert 'T141_REPORTED_RECEIPT_PDF_OK weights_unchanged=True' in (root/'qa-cerro-flow.log').read_text(encoding='utf-8-sig')
    body=('T141: recibo nativo de entrega/recepción adaptado para las entradas de fruta de Packing. '
          'Incluye logo y direcciones existentes, guía, tipo y clase de fruta, lote, operaciones, '
          'envases físicos, detalle de pallets con cajas y pesos bruto/tara/neto, promedio ponderado, '
          'totales y transporte/chofer. Se conservan el mismo acceso de impresión y el formato de '
          'documentos de stock ajenos a Packing. Probados y revisados visualmente PDFs cortos y '
          'multipágina, incluido el recibo real del adjunto en una copia de QA-Cerro. '
          'No se validaron recepciones reales ni cambiaron pesos, existencias o datos de capacitación. '
          'Mismo paquete publicado y verificado en Desarrollo, Cerro y QA-Cerro, con copias frescas, '
          'respaldo y bloqueo. Versión y código efectivo iguales en ambos Cerro; aislamiento y '
          'retiro de la excepción temporal al HTTP privado de informes comprobados. '
          'Pruebas aprobadas: '+str(expected['tests'])+'. Commit: '+expected['commit']+
          '; SHA-256: '+expected['sha256']+'.')
    c=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'));url='https://soporte.stepsapp.cl'
    uid=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(c['db'],c['username'],c['api_key'],{});assert uid
    rpc=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object');context={'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,'mail_notify_force_send':False,'mail_auto_subscribe_no_notify':True}
    def call(model,method,values,kw=None):return rpc.execute_kw(c['db'],uid,c['api_key'],model,method,values,dict({'context':context},**(kw or {})))
    for tid in (141,):
        ticket=call('helpdesk.ticket','read',[[tid]],{'fields':['stage_id','sla_ids','sla_status_ids']})[0]
        assert ticket['stage_id'][0] not in (4,5) and not ticket['sla_ids'] and not ticket['sla_status_ids']
        assert not call('mail.message','search_count',[[('model','=','helpdesk.ticket'),('res_id','=',tid),('id','>',expected['reviewed_messages'][str(tid)]),('message_type','in',['comment','email'])]])
    model=call('ir.model','search',[[('model','=','helpdesk.ticket')]])
    assert not call('base.automation','search_count',[[('model_id','in',model),('active','=',True)]])
    author=call('res.users','read',[[uid]],{'fields':['partner_id']})[0]['partner_id'][0]
    subtype=call('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
    for tid in (141,):
        domain=[('mail_message_id.model','=','helpdesk.ticket'),('mail_message_id.res_id','=',tid)]
        deliveries={m:set(call(m,'search',[domain])) for m in ('mail.notification','mail.mail')}
        message=call('mail.message','create',[{'model':'helpdesk.ticket','res_id':tid,'message_type':'comment','subtype_id':subtype,'author_id':author,'partner_ids':[(6,0,[])],'body':'<p>'+html.escape(body)+'</p>'}])
        call('helpdesk.ticket','write',[[tid],{'stage_id':4}])
        assert call('helpdesk.ticket','read',[[tid]],{'fields':['stage_id']})[0]['stage_id'][0]==4
        for model,ids in deliveries.items():assert set(call(model,'search',[domain]))==ids
        print('T%s_DELIVERY_RECORDED note=%s stage=4 NO_NOTIFICATIONS_OK'%(tid,message))


if __name__=='__main__':main()
