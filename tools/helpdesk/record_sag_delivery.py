"""Record T92 Development-only delivery after copy and actual UI verification."""
import argparse
import hashlib
import html
import json
import xmlrpc.client
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence', type=Path, required=True)
args = parser.parse_args()
proof = json.loads((args.evidence / 'visual-review.json').read_text(encoding='utf-8'))
assert proof['environment'] == 'development'
assert all(proof[key] for key in ('menu', 'list', 'form', 'tabs', 'ot_tarjas'))
qa = json.loads((args.evidence / 'development-qa.json').read_text(encoding='utf-8'))
assert qa['commit'] == proof['commit'] and qa['release_sha256'] == proof['release_sha256']
log = (args.evidence / 'development-deploy.log').read_text(encoding='utf-8')
assert proof['commit'] in log and 'MANAGEMENT_DEPLOY_OK backup=' in log and 'MANAGEMENT_VERIFY_OK' in log
assert proof['files']
for name, sha in proof['files'].items():
    assert hashlib.sha256((args.evidence / name).read_bytes()).hexdigest() == sha

cfg = json.loads((Path.home() / '.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
url = cfg['url'].rstrip('/')
uid = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/common').authenticate(cfg['db'], cfg['username'], cfg['api_key'], {})
server = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/object')

def rpc(model, method, arguments, keywords=None):
    return server.execute_kw(cfg['db'], uid, cfg['api_key'], model, method, arguments, keywords or {})

ticket = rpc('helpdesk.ticket', 'read', [[92]], {'fields': ['name', 'stage_id']})[0]
assert ticket['name'].startswith('T92 ')
author = rpc('res.users', 'read', [[uid]], {'fields': ['partner_id']})[0]['partner_id'][0]
note = rpc('ir.model.data', 'search_read', [[('module', '=', 'mail'), ('name', '=', 'mt_note')]], {'fields': ['res_id']})[0]['res_id']
marker = 'T92 Prototipo de inspección SAG publicado solo en Desarrollo'
recent = rpc('mail.message', 'search_read', [[('model', '=', 'helpdesk.ticket'), ('res_id', '=', 92),
    ('id', '>', 9504), ('message_type', 'in', ['comment', 'email'])]], {'fields': ['id', 'body', 'author_id', 'subtype_id']})
assert all(marker in (m['body'] or '') and m['author_id'] and m['author_id'][0] == author
    and m['subtype_id'] and m['subtype_id'][0] == note for m in recent), 'Read newer human replies first'
body = ('Prototipo disponible para QA en Desarrollo: Packing / Inspecciones / Inspección SAG. '
    'Basado en los dos adjuntos y el Manual para Externos Programa Origen SAG v04, 10-07-2024. '
    'Reutiliza la inspección nativa, la OT, las tarjas y los maestros existentes. Incluye preparación '
    'documental y física, destino, contraparte, solicitud externa, muestreo, laboratorio, tratamientos, '
    'resguardo, SIF y respaldos. La aprobación/rechazo externo exige evidencia y permisos; pendiente '
    'bloquea despacho para el destino y una reevaluación no hereda una aprobación anterior. '
    'Se probaron cuatro casos funcionales sobre una copia de Desarrollo con OT cerrada y movimientos '
    'reales aislados; después se verificaron el paquete instalado y el menú/formulario en navegador. '
    'Datos anteriores preservados y respaldo del ambiente. No se actualizó Cerro ni otra producción. '
    'No agenda servicios ni emite certificados oficiales: esas acciones siguen ante SAG. '
    'Alcance del prototipo: una OT, conjunto de tarjas y un país por registro; no reemplaza una SIF '
    'oficial con múltiples destinos ni verifica automáticamente requisitos vigentes de cada mercado. '
    'Queda entregado para revisión humana en Desarrollo.')
body = '<h3>' + marker + '</h3><p>' + html.escape(body) + '</p>'
existing = [m for m in recent if marker in (m['body'] or '')]
message = existing[0]['id'] if existing else rpc('mail.message', 'create', [{'model': 'helpdesk.ticket', 'res_id': 92,
    'message_type': 'comment', 'subtype_id': note, 'author_id': author, 'partner_ids': [(5, 0, 0)], 'body': body}])
assert not rpc('mail.message', 'read', [[message]], {'fields': ['notification_ids']})[0]['notification_ids']
rpc('helpdesk.ticket', 'write', [[92], {'stage_id': 4}], {'context': {'tracking_disable': True, 'mail_notrack': True,
    'mail_create_nosubscribe': True, 'mail_auto_subscribe_no_notify': True}})
print('T92_DELIVERY_RECORDED stage=4 note=' + str(message))
