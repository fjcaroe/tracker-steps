"""Resolve T175 silently after three native destination checks and PDF review."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import xmlrpc.client


def payloads(text,marker):
    return [json.loads(line[len(marker):]) for line in text.splitlines() if line.startswith(marker)]


def evidence(root,dates_review=False):
    identities=set()
    expected_tests=63 if dates_review else 56
    expected_version='18.0.1.0.2' if dates_review else '18.0.1.0.0'
    for target in ('development','cerro','qa-cerro'):
        proof=json.loads((root/(target+'-qa.json')).read_text())
        receipt=json.loads((root/(target+'-deployment.json')).read_text())
        assert (proof['commit'],proof['release_sha256'])==(receipt['commit'],receipt['sha256'])
        identities.add((proof['commit'],proof['release_sha256']))
        assert re.search(r'0 failed, 0 error\(s\) of '+str(expected_tests)+r' tests',(root/(target+'-qa.log')).read_text())
        clone,=payloads((root/(target+'-verify.log')).read_text(),'MANAGEMENT_REGISTRY_OK ')
        live_text=(root/(target+'-live.log')).read_text()
        live,=payloads(live_text,'MANAGEMENT_REGISTRY_OK ')
        assert 'MANAGEMENT_DEPLOY_OK backup=' in live_text and 'MANAGEMENT_VERIFY_OK ' in live_text
        for result in (clone,live):
            assert result['ticket']==175 and result['live_business_writes'] is False
            assert result['versions']=={'step_packing_fruit_proforma':'18.0.1.2.0','step_producer_advances':expected_version}
            assert all(result['ui'].values())
        flow=clone['copy_flow']
        assert set(flow['documents'])=={'33','46'} and flow['large_annex_rows']==1000
        assert all(flow[key] is True for key in ('late_process','packed_reception','native_invoice_drafts',
            'two_payment_dates','idempotent','stock_preserved','no_official_folio'))
        if dates_review and target=='cerro':
            plan_bytes=(root/'t175-date-case.json').read_bytes()
            plan=json.loads(plan_bytes);case=clone['reported_dates'];readback=live['reported_dates']
            assert case['copy_flow'] and case['idempotent'] and readback['copy_flow'] is False
            assert case['recovered_receipts']==plan['recovered_receipts'] and case['recovered_kilos']==plan['recovered_kilos']
            assert case['plan_sha256']==readback['plan_sha256']==hashlib.sha256(plan_bytes).hexdigest()
        purchase=json.loads((root/(target+'-purchase-preservation.json')).read_text())
        assert purchase['original_columns_preserved'] and purchase['release_sha256']==proof['release_sha256']
        review=json.loads((root/(target+'-pdf-review.json')).read_text(encoding='utf-8-sig'))
        assert review['reviewed'] is True
        for filename,suffix in [('t175-smoke-advances.pdf','smoke.pdf'),('t175-large-advance.pdf','large.pdf')]:
            assert review['files'][filename]['sha256']==hashlib.sha256((root/(target+'-'+suffix)).read_bytes()).hexdigest()
            assert review['files'][filename]['pages']
    assert len(identities)==1
    pair,=payloads((root/'pair.log').read_text(),'CERRO_RELEASE_PAIR_OK ')
    for module in ('step_packing_fruit_proforma','step_producer_advances'):
        assert pair['cerro'][module]['sha256']==pair['qa-cerro'][module]['sha256']
    isolation=(root/'isolation.log').read_text()
    assert all(marker in isolation for marker in ('CUSTOMER_QA_VERIFY_OK','CUSTOMER_QA_EGRESS_BLOCKED','CUSTOMER_QA_SOURCE_DB_DENIED'))
    return next(iter(identities))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('evidence',type=Path)
    parser.add_argument('--dates-review',action='store_true')
    args=parser.parse_args();commit,sha=evidence(args.evidence,args.dates_review)
    config=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
    url='https://soporte.stepsapp.cl'
    uid=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(config['db'],config['username'],config['api_key'],{})
    assert uid
    rpc=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object')
    context={'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,
             'mail_notify_force_send':False,'mail_auto_subscribe_no_notify':True}
    def call(model,method,values,kwargs=None):
        return rpc.execute_kw(config['db'],uid,config['api_key'],model,method,values,dict({'context':context},**(kwargs or {})))
    ticket=call('helpdesk.ticket','read',[[175]],{'fields':['stage_id','sla_ids','sla_status_ids']})[0]
    assert ticket['stage_id'][0]==2 and not ticket['sla_ids'] and not ticket['sla_status_ids']
    model=call('ir.model','search',[[('model','=','helpdesk.ticket')]])
    assert not call('base.automation','search_count',[[('model_id','in',model),('active','=',True)]])
    reviewed_message=10210 if args.dates_review else 10205
    new=call('mail.message','search_read',[[('model','=','helpdesk.ticket'),('res_id','=',175),('id','>',reviewed_message)]],
             {'fields':['id','message_type','attachment_ids']})
    assert not [row['id'] for row in new if row['message_type'] in ('comment','email') or row['attachment_ids']], 'Read new replies first'
    author=call('res.users','read',[[uid]],{'fields':['partner_id']})[0]['partner_id'][0]
    subtype=call('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
    body=('Anticipos semanales disponibles en Productores > Anticipos, en Desarrollo, Cerro producción y QA-Cerro. '
          'Listas de precios por empresa, especie, producto, mercado y embalaje. Preparación por productor y especie, '
          'con fechas de recepción, corte de proceso y pagos separados del neto e IVA. Incluye fruta recibida en crudo '
          'y procesada posteriormente, y recepción directa embalada; conserva trazabilidad por guía, OT y tarja, '
          'sin anticipar dos veces la misma recepción. Proforma con resumen y anexo, validación y creación del '
          'borrador contable nativo según DTE 33/46 e impuestos configurados. '
          'Se respetan las proformas mensuales y los maestros existentes. No se cargaron precios ilustrativos ni '
          'se emitieron documentos fiscales. El responsable debe configurar y revisar sus tarifas antes del primer anticipo. '
          '168 pruebas sin errores en copias frescas, flujo con usuario operativo, pagos y PDF de 1.000 filas revisados. '
          'Compras originales preservadas; publicación con respaldo y aislamiento de QA-Cerro comprobado. '
          'Referencia: '+commit+'; paquete '+sha+'.')
    if args.dates_review:
        body=('Revisión 1 aplicada en Desarrollo, Cerro y QA-Cerro. La recepción se imputa a la fecha '
              'más antigua entre la prevista y la efectiva; esa fecha también determina la vigencia del precio. '
              'El corte usa la fecha de packing de la OT. Para recepciones históricas sin fundo, se acepta el '
              'productor de la recepción si coincide con la tarja. Una tarja sin embalaje puede usar el único '
              'embalaje maestro disponible de su producto. Se conservan tarjas, maestros y precios. '
              'En la copia del caso real, se prepararon cinco recepciones adicionales por 3.981 kg con la lista '
              'ya configurada. Repetir la preparación con los mismos parámetros permite incorporar los kilos, '
              'conservando el control de duplicados. No se modificaron anticipos reales durante la publicación. '
              '189 pruebas aprobadas; se verificaron PDF, formularios, origen, respaldo y aislamiento. '
              'Referencia: '+commit+'; paquete '+sha+'.')
    domain=[('model','=','helpdesk.ticket'),('res_id','=',175)]
    messages=set(call('mail.message','search',[domain]))
    deliveries=[('mail_message_id.model','=','helpdesk.ticket'),('mail_message_id.res_id','=',175)]
    before={name:set(call(name,'search',[deliveries])) for name in ('mail.notification','mail.mail')}
    note=call('mail.message','create',[{'model':'helpdesk.ticket','res_id':175,'message_type':'comment',
        'subtype_id':subtype,'author_id':author,'partner_ids':[(6,0,[])],'body':'<p>'+html.escape(body)+'</p>'}])
    call('helpdesk.ticket','write',[[175],{'stage_id':4}])
    assert call('helpdesk.ticket','read',[[175]],{'fields':['stage_id']})[0]['stage_id'][0]==4
    assert set(call('mail.message','search',[domain]))==messages|{note}
    for name in before:assert set(call(name,'search',[deliveries]))==before[name]
    print('T175_DELIVERY_RECORDED note=%s stage=4 NO_NOTIFICATIONS_OK'%note)


if __name__=='__main__':main()
