"""Record T94 Development-only delivery after copy and actual UI verification."""
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
assert all(proof[key] for key in ('menu', 'list', 'form', 'seven_stages', 'process_navigation', 'search'))
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

ticket = rpc('helpdesk.ticket', 'read', [[94]], {'fields': ['name', 'stage_id']})[0]
assert ticket['name'].startswith('T94 ')
author = rpc('res.users', 'read', [[uid]], {'fields': ['partner_id']})[0]['partner_id'][0]
note = rpc('ir.model.data', 'search_read', [[('module', '=', 'mail'), ('name', '=', 'mt_note')]], {'fields': ['res_id']})[0]['res_id']
marker = 'T94 Trazabilidad por pallet publicada solo en Desarrollo'
recent = rpc('mail.message', 'search_read', [[('model', '=', 'helpdesk.ticket'), ('res_id', '=', 94),
    ('id', '>', 9516), ('message_type', 'in', ['comment', 'email'])]], {'fields': ['id', 'body', 'author_id', 'subtype_id']})
assert all(marker in (m['body'] or '') and m['author_id'] and m['author_id'][0] == author
    and m['subtype_id'] and m['subtype_id'][0] == note for m in recent), 'Read newer human replies first'
body = ('Entrega disponible para revisión en Desarrollo, Exportaciones / Recibidor / Trazabilidad. '
    'La consulta ahora parte del folio pallet, con un panel de las siete etapas del documento: productor, '
    'recepción, embalado, calidad, despacho, exportación y recibidor. Las referencias abren los procesos '
    'y documentos originales. Incluye la genealogía de OT y repaletizajes validados, y un listado de '
    'varias tarjas con los detalles de cada etapa exportables mediante Odoo. '
    'Conserva los registros y permisos existentes; los datos sin evidencia disponible se muestran como '
    'Sin registro. La calidad de llegada se selecciona del catálogo existente en el embarque. '
    'Las fechas de arribo son las registradas en el embarque. Se probó el mismo paquete en copia fresca, '
    'con respaldo antes de publicar y verificación funcional posterior y en navegador. '
    'No se publicó en producción. Queda entregado para revisión humana en Desarrollo.')
body = '<h3>' + marker + '</h3><p>' + html.escape(body) + '</p>'
existing = [m for m in recent if marker in (m['body'] or '')]
message = existing[0]['id'] if existing else rpc('mail.message', 'create', [{'model': 'helpdesk.ticket', 'res_id': 94,
    'message_type': 'comment', 'subtype_id': note, 'author_id': author, 'partner_ids': [(5, 0, 0)], 'body': body}])
assert not rpc('mail.message', 'read', [[message]], {'fields': ['notification_ids']})[0]['notification_ids']
rpc('helpdesk.ticket', 'write', [[94], {'stage_id': 4}], {'context': {'tracking_disable': True, 'mail_notrack': True,
    'mail_create_nosubscribe': True, 'mail_auto_subscribe_no_notify': True}})
assert rpc('helpdesk.ticket', 'read', [[94]], {'fields': ['stage_id']})[0]['stage_id'][0] == 4
print('T94_DELIVERY_RECORDED stage=4 note=' + str(message))
