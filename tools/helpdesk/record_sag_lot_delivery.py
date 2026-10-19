"""Record T93 Development-only delivery after copy and actual UI verification."""
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
assert all(proof[key] for key in ('menu', 'list', 'form', 'tabs', 'multi_ot_fields', 'reports_rendered'))
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

ticket = rpc('helpdesk.ticket', 'read', [[93]], {'fields': ['name', 'stage_id']})[0]
assert ticket['name'].startswith('T93 ')
author = rpc('res.users', 'read', [[uid]], {'fields': ['partner_id']})[0]['partner_id'][0]
note = rpc('ir.model.data', 'search_read', [[('module', '=', 'mail'), ('name', '=', 'mt_note')]], {'fields': ['res_id']})[0]['res_id']
marker = 'T93 Lotes SAG y archivos de despacho publicados solo en Desarrollo'
recent = rpc('mail.message', 'search_read', [[('model', '=', 'helpdesk.ticket'), ('res_id', '=', 93),
    ('id', '>', 9508), ('message_type', 'in', ['comment', 'email'])]], {'fields': ['id', 'body', 'author_id', 'subtype_id']})
assert all(marker in (m['body'] or '') and m['author_id'] and m['author_id'][0] == author
    and m['subtype_id'] and m['subtype_id'][0] == note for m in recent), 'Read newer human replies first'
body = ('Entrega disponible para QA solo en Desarrollo, Packing / Inspecciones / Inspección SAG. '
    'Incorpora tipo de fruta convencional/orgánico, recibidor, instructivo y tabla de tipos de servicio. '
    'El lote admite varias OT y productores de una especie; el productor se conserva por tarja, fuera del encabezado. '
    'Permite seleccionar, ingresar o leer los folios de los códigos impresos, filtrados por especie, variedades, '
    'stock validado, inspecciones anteriores, tipo de fruta e instructivo. '
    'Genera INS, INT, REP, DET y DES según el servicio y Anexo 5 adjunto; valida códigos oficiales y longitudes, '
    'sin truncar identificadores ni generar coincidencias de folio. '
    'Genera anexo de planilla de despacho en Excel y PDF con folios, especies, variedades, provincia/comuna, '
    'envases, fechas, destinos, productores y total. Se revisó también el PDF de varias páginas. '
    'Se probó el paquete exacto en copia fresca del destino, se conservaron los datos anteriores y se respaldó '
    'Desarrollo antes de actualizar. Se verificaron el registro instalado y la navegación en navegador. '
    'Los archivos no se envían automáticamente al SAG ni ejecutan anulaciones o movimientos de inventario. '
    'La planilla oficial se emite/regulariza en Multipuerto. Los códigos y orígenes faltantes deben completarse '
    'en los maestros existentes; el sistema no inventa códigos SAG, provincias ni comunas. '
    'No se publicó en producción. Queda entregado para revisión humana en Desarrollo.')
body = '<h3>' + marker + '</h3><p>' + html.escape(body) + '</p>'
existing = [m for m in recent if marker in (m['body'] or '')]
message = existing[0]['id'] if existing else rpc('mail.message', 'create', [{'model': 'helpdesk.ticket', 'res_id': 93,
    'message_type': 'comment', 'subtype_id': note, 'author_id': author, 'partner_ids': [(5, 0, 0)], 'body': body}])
assert not rpc('mail.message', 'read', [[message]], {'fields': ['notification_ids']})[0]['notification_ids']
rpc('helpdesk.ticket', 'write', [[92], {'stage_id': 4}], {'context': {'tracking_disable': True, 'mail_notrack': True,
    'mail_create_nosubscribe': True, 'mail_auto_subscribe_no_notify': True}})
print('T93_DELIVERY_RECORDED stage=4 note=' + str(message))
