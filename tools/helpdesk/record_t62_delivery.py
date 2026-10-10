"""Record T62's verified result as an internal journal entry without notifying followers."""
import json
from pathlib import Path
import xmlrpc.client


def main():
    config = json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
    url = config.get('url', 'https://soporte.stepsapp.cl').rstrip('/')
    assert url.startswith('https://')
    uid = xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(config['db'],config['username'],config['api_key'],{})
    assert uid
    obj = xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object')
    def rpc(model, method, args, kwargs=None):
        return obj.execute_kw(config['db'],uid,config['api_key'],model,method,args,kwargs or {})
    marker = 'T62 - formato publicado ade6e0a'
    previous = rpc('mail.message','search_read',[[('model','=','helpdesk.ticket'),('res_id','=',62),('body','ilike',marker)]],{'fields':['id','subtype_id']})
    if previous:
        print('T62_INTERNAL_EVIDENCE_EXISTS', previous[0]['id'])
        return
    assert rpc('helpdesk.ticket','read',[[62]],{'fields':['name']})[0]['name'].startswith('T62')
    note = rpc('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
    author = rpc('res.users','read',[[uid]],{'fields':['partner_id']})[0]['partner_id'][0]
    body = '''<h3>T62 - formato publicado ade6e0a</h3>
<p>Nota de venta y Proforma implementadas según el formato adjunto y publicadas en
<a href="https://cerroelplomo.stepsapp.cl/odoo/action-1458">Cerro El Plomo</a>, para la empresa Cerro El Plomo SpA.
Incluyen kilos, cajas, detalle del producto, Incoterm, embarque, observaciones y desglose de flete/seguro con el total de Odoo.</p>
<p>Primero se probó y publicó en Desarrollo. Una copia fresca de Cerro pasó cinco pruebas,
conservación de registros, formulario, menú y flujo de vendedor, ambos PDF y pedido de varias páginas.
Se repitieron esas verificaciones después de publicar y se revisó el formulario en Chrome.</p>
<p><strong>Pendiente de configuración bancaria:</strong> el adjunto menciona AVOS AMERICA INC y deja cuenta, SWIFT y ABA vacíos.
Es necesario confirmar la instrucción de pago antes de seleccionar una cuenta real. La sección bancaria queda disponible en la empresa;
no se han guardado cuentas de prueba ni inventado datos de cobro.</p>
<p>Prueba financiera: descuento, flete y seguro conciliados con total de 215 USD.
Módulo step_sale_export_report 18.0.1.0.0; paquete ade6e0a2ec064a55643727b20913bc737d470444;
SHA256 c6f8634c2c076e9991ddcab1867daec304343101c8d0fb979d462d34cb111155.</p>
<p>Respaldo de Cerro: /opt/steps_backups/management_cerro_20261010T002012Z.
Código y acta están subidos e integrados en la rama canónica.
<a href="https://github.com/fjcaroe/tracker-steps/blob/codex/ambientes-canonicos-reparacion/docs/T62_NOTA_VENTA_PROFORMA_2026-10-09.rst">Acta técnica y uso</a>.</p>
<p>El ticket permanece en seguimiento por la definición bancaria. Esta evidencia es interna.</p>'''
    message = rpc('mail.message','create',[{'model':'helpdesk.ticket','res_id':62,'message_type':'comment',
        'subtype_id':note,'author_id':author,'body':body,'partner_ids':[(5,0,0)]}])
    context = {'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,'mail_auto_subscribe_no_notify':True}
    rpc('helpdesk.ticket','write',[[62],{'stage_id':2}],{'context':context})
    saved = rpc('mail.message','read',[[message]],{'fields':['body','subtype_id','notification_ids']})[0]
    assert marker in saved['body'] and saved['subtype_id'][0] == note and not saved['notification_ids']
    ticket = rpc('helpdesk.ticket','read',[[62]],{'fields':['stage_id']})[0]
    assert ticket['stage_id'][0] == 2
    print('T62_INTERNAL_EVIDENCE_OK', message, 'stage=In Progress', 'notifications=0')


if __name__ == '__main__':
    main()
