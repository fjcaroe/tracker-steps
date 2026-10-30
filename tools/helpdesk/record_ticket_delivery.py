"""Silently record reviewed T141–T144 delivery after complete functional evidence."""
import argparse
import html
import hashlib
import json
from pathlib import Path
import re
import xmlrpc.client


DESCRIPTIONS={
 141:'El título del recibo muestra RECIBO DE RECEPCIÓN N° seguido del folio nativo de recepción. Revisados los PDF corto, multipágina y del caso reportado; pesos y datos conservados.',
 142:'Compras holding: Entregar a permite seleccionar una sucursal de la misma raíz legal entre las compañías activas del comprador. Seleccionar antes de ingresar productos. El pedido, sus líneas y la recepción quedan en esa sucursal y el formulario muestra su dirección. Probado el ingreso de existencias en copia. Sin ampliación de permisos ni compras reales durante la publicación.',
 143:'Implementada la alternativa b solicitada: permite eliminar manualmente asistencias validadas cuando todas las liquidaciones correspondientes están en borrador, sin pago, bloqueo histórico ni asiento publicado. Luego se puede corregir la fecha del contrato y recalcular el borrador. Licencias, ausencias y liquidaciones confirmadas conservan sus bloqueos. El caso reportado ya figura confirmado en SyS: se comprobó su protección en copia y se conservaron su liquidación, contrato y asistencias reales.',
 144:'Las tarjas E/N resultantes conservan la compañía de su OT aun sin existencias, permitiendo filtrar por sucursal. Completadas las compañías vacías de tarjas vinculadas a una OT. Ubicaciones, cantidades, estados e IDs conservados; se rechazan contradicciones con la compañía del stock. No se validaron OT ni se generaron existencias reales.',
}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('ticket',type=int,choices=tuple(DESCRIPTIONS));p.add_argument('evidence',type=Path);a=p.parse_args()
    root=a.evidence;proof=json.loads((root/'delivery.json').read_text());tid=a.ticket
    module={141:'step_packing_reception_report',142:'step_purchase_holding',143:'step_payroll_attendance_correction',144:'step_packing_tag_company'}[tid]
    environments={'development','cerro','qa-cerro'}|({'sys'} if tid==143 else set())
    for target in environments:
        qa=json.loads((root/(target+'-qa.json')).read_text());deployment=json.loads((root/(target+'-deployment.json')).read_text())
        assert qa['commit']==deployment['commit']==proof['commit'] and qa['release_sha256']==deployment['sha256']==proof['sha256']
        assert re.search(r'0 failed, 0 error\(s\) of [1-9][0-9]* tests',(root/(target+'-qa.log')).read_text(encoding='utf-8-sig'))
        assert 'MANAGEMENT_VERIFY_OK' in (root/(target+'-live.log')).read_text(encoding='utf-8-sig')
    pair=json.loads((root/'pair.json').read_text());assert all(pair['cerro'][module][key]==pair['qa-cerro'][module][key] for key in ('version','sha256'))
    assert all(marker in (root/'isolation.log').read_text() for marker in ('CUSTOMER_QA_VERIFY_OK','CUSTOMER_QA_EGRESS_BLOCKED','CUSTOMER_QA_SOURCE_DB_DENIED'))
    if tid==141:
        assert pair['cerro'][module]['version']=='18.0.1.0.2'
        for target in environments:
            review=json.loads((root/(target+'-visual-review.json')).read_text(encoding='utf-8-sig'))
            assert review['reviewed'] is True
            for name,item in review['files'].items():
                assert hashlib.sha256((root/(target+'-'+name)).read_bytes()).hexdigest()==item['sha256']
            assert 'T141_NATIVE_PDF_OK' in (root/(target+'-flow.log')).read_text(encoding='utf-8-sig')
        assert 'T141_REPORTED_RECEIPT_PDF_OK weights_unchanged=True' in (root/'qa-cerro-flow.log').read_text(encoding='utf-8-sig')
    c=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'));url='https://soporte.stepsapp.cl'
    uid=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(c['db'],c['username'],c['api_key'],{});assert uid
    rpc=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object');context={'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,'mail_notify_force_send':False,'mail_auto_subscribe_no_notify':True}
    def call(model,method,values,kw=None):return rpc.execute_kw(c['db'],uid,c['api_key'],model,method,values,dict({'context':context},**(kw or {})))
    ticket=call('helpdesk.ticket','read',[[tid]],{'fields':['stage_id','sla_ids','sla_status_ids']})[0]
    assert ticket['stage_id'][0] not in (4,5) and not ticket['sla_ids'] and not ticket['sla_status_ids']
    assert not call('mail.message','search_count',[[('model','=','helpdesk.ticket'),('res_id','=',tid),('id','>',proof['reviewed_messages'][str(tid)]),('message_type','in',['comment','email'])]]), 'Review new human responses before closure'
    model=call('ir.model','search',[[('model','=','helpdesk.ticket')]])
    assert not call('base.automation','search_count',[[('model_id','in',model),('active','=',True)]])
    author=call('res.users','read',[[uid]],{'fields':['partner_id']})[0]['partner_id'][0]
    subtype=call('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
    domain=[('mail_message_id.model','=','helpdesk.ticket'),('mail_message_id.res_id','=',tid)]
    deliveries={m:set(call(m,'search',[domain])) for m in ('mail.notification','mail.mail')}
    body=DESCRIPTIONS[tid]+' Publicado y verificado en '+', '.join(sorted(environments))+'. Mismo paquete, copias frescas, respaldo y bloqueo compartido. Paridad del módulo entre Cerro y QA-Cerro y aislamiento verificados. Pruebas: '+str(proof['tests'])+'. Commit: '+proof['commit']+'; SHA-256: '+proof['sha256']+'.'
    message=call('mail.message','create',[{'model':'helpdesk.ticket','res_id':tid,'message_type':'comment','subtype_id':subtype,'author_id':author,'partner_ids':[(6,0,[])],'body':'<p>'+html.escape(body)+'</p>'}])
    call('helpdesk.ticket','write',[[tid],{'stage_id':4}])
    assert call('helpdesk.ticket','read',[[tid]],{'fields':['stage_id']})[0]['stage_id'][0]==4
    for model,ids in deliveries.items():assert set(call(model,'search',[domain]))==ids
    print('T%s_DELIVERY_RECORDED note=%s stage=4 NO_NOTIFICATIONS_OK'%(tid,message))


if __name__=='__main__':main()
