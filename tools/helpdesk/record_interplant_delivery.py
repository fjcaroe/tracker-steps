"""Register only fully verified T207/T208 deliveries as silent internal notes."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import xmlrpc.client

DESCRIPTIONS = {
209: "Corregido el almacén de destino en las guías interplanta cuando solo está activa la sucursal de origen. Se muestran los almacenes de la planta destinataria autorizada; si hay uno se propone automáticamente y si hay varios permite elegir. Las guías en borrador también resuelven el almacén único al confirmar. Se mantiene la recepción pendiente de validar y no se amplían permisos ni se modifican guías del cliente como parte de la publicación.",
207: 'En Packing / Despacho, Tipo despacho aparece antes del destinatario y filtra clientes, productores o empresas y sucursales relacionadas. Folio Pallet permite seleccionar tarjas C, E y N con stock libre, mostrando tipo, número, productor, cajas y kilos. Use Traer detalle de pallets antes de confirmar. El traslado interplanta registra la salida nativa y crea una recepción pendiente en Packing / Recepciones / Recepciones interplanta. El destino debe validar la llegada para disponer del stock. Conserva folios, lotes, propietario, cantidades y vínculo con la tarja original. Incluye traslados de materiales y conserva el despacho mediante instructivo de exportación.',
208: 'Las recepciones con devolución realizada quedan excluidas de los listados vigentes de fruta a proceso y embalada, incluso al usar búsquedas guardadas, y de sus informes dinámicos. El documento original y su devolución permanecen en Inventario y conservan su trazabilidad. El panel de tarjas se mantiene. Se verificó el caso reportado de 799,50 kg sin alterar movimientos ni existencias.'}

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('ticket', type=int, choices=DESCRIPTIONS)
parser.add_argument('evidence', type=Path)
args = parser.parse_args()
proof = json.loads((args.evidence / 'delivery.json').read_text(encoding='utf-8'))
assert proof['complete'] is True and proof['tests'] >= (66 if args.ticket == 209 else 57)
assert set(proof['targets']) == {'development', 'cerro', 'qa-cerro'}
assert hashlib.sha256((args.evidence / 'release.tar.gz').read_bytes()).hexdigest() == proof['sha256']
for target in proof['targets']:
    item = proof['targets'][target]
    assert item['deployed'] and item['version_form_menu_flow'] and item['backup']
    assert item['sha256'] == proof['sha256']
    ui = json.loads((args.evidence / target / 'ui-result.json').read_text())
    if args.ticket == 209:
        dest = json.loads((args.evidence / target / 'destination-ui-result.json').read_text(encoding='utf-8'))
        assert dest['destinationWarehouseChoices'] and dest['sourceCompanyUnchanged'] and not dest['errors']
    assert ui['currentReceiptFilter'] and ui['receptionPivot'] and ui['interplantMenu'] and ui['typeBeforeRecipient'] and not ui['errors']
assert proof['parity'] and proof['qa_isolation'] and proof['customer_case']
if args.ticket == 209:
    assert proof['reported_draft']['destination_pending'] and proof['reported_draft']['source_scope_unchanged']
cfg = json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
url = 'https://soporte.stepsapp.cl/xmlrpc/2/'
uid = xmlrpc.client.ServerProxy(url+'common').authenticate(cfg['db'],cfg['username'],cfg['api_key'],{})
assert uid
rpc = xmlrpc.client.ServerProxy(url+'object')
context = {'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,
           'mail_notify_force_send':False,'mail_auto_subscribe_no_notify':True}
def call(model, method, values, kwargs=None):
    return rpc.execute_kw(cfg['db'],uid,cfg['api_key'],model,method,values,dict({'context':context},**(kwargs or {})))
ticket = call('helpdesk.ticket','read',[[args.ticket]],{'fields':['stage_id','sla_ids','sla_status_ids']})[0]
assert ticket['stage_id'][0] == 2 and not ticket['sla_ids'] and not ticket['sla_status_ids']
assert not call('mail.message','search_count',[[('model','=','helpdesk.ticket'),('res_id','=',args.ticket),
    ('id','>',proof['reviewed_messages'][str(args.ticket)]),('message_type','in',['comment','email'])]]), 'Read new human responses first'
model = call('ir.model','search',[[('model','=','helpdesk.ticket')]])
assert not call('base.automation','search_count',[[('model_id','in',model),('active','=',True)]])
author = call('res.users','read',[[uid]],{'fields':['partner_id']})[0]['partner_id'][0]
subtype = call('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
domain = [('mail_message_id.model','=','helpdesk.ticket'),('mail_message_id.res_id','=',args.ticket)]
before = {model:set(call(model,'search',[domain])) for model in ('mail.notification','mail.mail')}
body = DESCRIPTIONS[args.ticket] + ' Publicado y verificado en Desarrollo, Cerro producción y QA-Cerro. '
versions = proof.get('versions', {'step_packing_interplant':'18.0.1.0.0','step_packing_ticket_revision':'18.0.1.2.5'})
body += 'Versiones: ' + ', '.join(name + ' ' + version for name, version in versions.items()) + '. '
body += str(proof['tests']) + ' pruebas correctas en copias frescas, más caso real en copia; revisión visual, respaldos, paridad y aislamiento verificados. '
body += 'Paquete ' + proof['commit'] + '; SHA-256 ' + proof['sha256'] + '.'
message = call('mail.message','create',[{'model':'helpdesk.ticket','res_id':args.ticket,
    'message_type':'comment','subtype_id':subtype,'author_id':author,'partner_ids':[(6,0,[])],
    'body':'<p>'+html.escape(body)+'</p>'}])
call('helpdesk.ticket','write',[[args.ticket],{'stage_id':4}])
assert call('helpdesk.ticket','read',[[args.ticket]],{'fields':['stage_id']})[0]['stage_id'][0] == 4
for model, ids in before.items():
    assert set(call(model,'search',[domain])) == ids
print('TICKET_DELIVERED ticket=%s note=%s NO_NOTIFICATIONS_OK' % (args.ticket,message))
