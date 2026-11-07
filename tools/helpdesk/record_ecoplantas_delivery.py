"""Close T176 only after independent native setup, copy workflow and HTTPS proof."""
import argparse
import html
import json
from pathlib import Path
import xmlrpc.client


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('evidence',type=Path)
    args=parser.parse_args();root=args.evidence
    prepared=json.loads((root/'prepared.json').read_text())
    copy=json.loads((root/'copy-verified.json').read_text())
    live=json.loads((root/'verified.json').read_text())
    published=json.loads((root/'published.json').read_text())
    assert prepared['ticket']==176 and prepared['license_copied'] is False
    assert copy['database']=='ECOPLANTAS_T176_QA' and live['database']=='ECOPLANTAS'
    for proof in (copy,live):
        assert proof['license_copied'] is False and proof['source_client_data_copied'] is False
        assert all(proof[key] is True for key in ('native_menus_and_forms','unique_uuid',
            'existing_admin_preserved','source_database_denied','private_native_addons'))
        assert not any(proof['empty_business_counts'].values())
    assert all(copy[key] is True for key in ('copy_flow','purchase_receipt_sale_delivery','native_vendor_bill_draft'))
    assert live['copy_flow'] is False
    assert published['url']=='https://ecoplantas.stepsapp.cl' and published['database']=='ECOPLANTAS'
    assert published['license_copied'] is False and published['backup']
    log=(root/'publish.log').read_text()
    assert 'ECOPLANTAS_PUBLISHED https://ecoplantas.stepsapp.cl' in log
    c=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
    url='https://soporte.stepsapp.cl'
    uid=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(c['db'],c['username'],c['api_key'],{})
    assert uid;rpc=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object')
    context={'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,
             'mail_notify_force_send':False,'mail_auto_subscribe_no_notify':True}
    def call(model,method,values,kwargs=None):
        return rpc.execute_kw(c['db'],uid,c['api_key'],model,method,values,dict({'context':context},**(kwargs or {})))
    ticket=call('helpdesk.ticket','read',[[176]],{'fields':['stage_id','sla_ids','sla_status_ids']})[0]
    assert ticket['stage_id'][0]==2 and not ticket['sla_ids'] and not ticket['sla_status_ids']
    model=call('ir.model','search',[[('model','=','helpdesk.ticket')]])
    assert not call('base.automation','search_count',[[('model_id','in',model),('active','=',True)]])
    new=call('mail.message','search_read',[[('model','=','helpdesk.ticket'),('res_id','=',176),('id','>',10207)]],
             {'fields':['id','message_type','attachment_ids']})
    assert not [row['id'] for row in new if row['message_type'] in ('comment','email') or row['attachment_ids']], 'Read new replies first'
    author=call('res.users','read',[[uid]],{'fields':['partner_id']})[0]['partner_id'][0]
    subtype=call('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
    body=('ECOPLANTAS disponible en https://ecoplantas.stepsapp.cl como base independiente de demostración, '
          'según la opción confirmada por el solicitante en el chat. Edición Enterprise nativa, con contactos, CRM, '
          'ventas, compras, inventario y contabilidad chilena. Base nueva sin movimientos ni datos de clientes. '
          'Ingreso con la identidad administrativa existente de Desarrollo, sin cambiar su contraseña. '
          'La suscripción de Desarrollo se conserva allí: no se copiaron códigos de activación, UUID ni vencimientos. '
          'La nueva base conserva su registro nativo propio de demostración. '
          'Servicio, código, almacenamiento y acceso a base de datos separados; el usuario del nuevo servicio '
          'no puede abrir Desarrollo. Correo y tareas automáticas desactivados. '
          'Se probaron formularios y menús con un usuario nativo y, en copia privada, compra, recepción, venta, '
          'despacho y factura de proveedor en borrador, sin dejar esos datos en la demo. HTTPS y servicio verificados; '
          'respaldo inicial conservado. No modifica los ambientes productivos ni la política de QA de Desarrollo.')
    domain=[('model','=','helpdesk.ticket'),('res_id','=',176)]
    original=set(call('mail.message','search',[domain]))
    deliveries=[('mail_message_id.model','=','helpdesk.ticket'),('mail_message_id.res_id','=',176)]
    before={name:set(call(name,'search',[deliveries])) for name in ('mail.notification','mail.mail')}
    note=call('mail.message','create',[{'model':'helpdesk.ticket','res_id':176,'message_type':'comment','subtype_id':subtype,
        'author_id':author,'partner_ids':[(6,0,[])],'body':'<p>'+html.escape(body)+'</p>'}])
    call('helpdesk.ticket','write',[[176],{'stage_id':4}])
    assert call('helpdesk.ticket','read',[[176]],{'fields':['stage_id']})[0]['stage_id'][0]==4
    assert set(call('mail.message','search',[domain]))==original|{note}
    for name in before:assert set(call(name,'search',[deliveries]))==before[name]
    print('T176_DELIVERY_RECORDED note=%s stage=4 NO_NOTIFICATIONS_OK'%note)


if __name__=='__main__':main()
