"""Record T82 delivery only after both destinations passed exact package/flow checks."""
import argparse
import html
import json
from pathlib import Path
import re
import xmlrpc.client

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--evidence', type=Path, required=True)
p.add_argument('--commit', required=True)
p.add_argument('--last-human-message', type=int, required=True)
args = p.parse_args()
assert re.fullmatch('[0-9a-f]{40}', args.commit)
required = ('menus', 'forms', 'new_form_onchange', 'preview_conversion',
            'manual_clp_usd', 'previous_state', 'analytic_selector', 'posting',
            'balanced', 'daily_rate', 'three_analytic_plans', 'duplicate_prevented')
for name, db in (('development', 'LAB_TAREAS'), ('cerro', 'CERRO_EL_PLOMO')):
    folder = args.evidence / name
    qa = json.loads((folder / 'qa_passed.json').read_text(encoding='utf-8'))
    deployment = json.loads((folder / 'deployment.json').read_text(encoding='utf-8'))
    assert qa['commit'] == deployment['commit'] == args.commit
    assert qa['release_sha256'] == deployment['sha256']
    lines = (folder / ('verify-' + db + '.log')).read_text(encoding='utf-8').splitlines()
    rows = [line for line in lines if line.startswith('MANAGEMENT_REGISTRY_OK ')]
    assert len(rows) == 1
    flow = json.loads(rows[0].split(' ', 1)[1])
    assert flow['ticket'] == 82 and all(flow[key] for key in required)

c = json.loads((Path.home() / '.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
url = c.get('url', 'https://soporte.stepsapp.cl').rstrip('/')
assert url.startswith('https://')
uid = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/common').authenticate(c['db'], c['username'], c['api_key'], {})
assert uid
s = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/object')
def rpc(model, method, values, kwargs=None):
    return s.execute_kw(c['db'], uid, c['api_key'], model, method, values, kwargs or {})

marker = 'T82 - correcciones publicadas y verificadas'
recent = rpc('mail.message', 'search_read', [[('model', '=', 'helpdesk.ticket'),
    ('res_id', '=', 82), ('message_type', 'in', ['comment', 'email']),
    ('id', '>', args.last_human_message)]], {'fields': ['id', 'body']})
assert not [m for m in recent if marker not in (m.get('body') or '')], 'Revisar respuestas nuevas antes de actualizar'
ticket = rpc('helpdesk.ticket', 'read', [[82]], {'fields': ['name', 'stage_id']})[0]
assert ticket['name'].startswith('T82') and ticket['stage_id'][0] in (1, 2, 6)
note = rpc('ir.model.data', 'search_read', [[('module', '=', 'mail'), ('name', '=', 'mt_note')]], {'fields': ['res_id']})[0]['res_id']
author = rpc('res.users', 'read', [[uid]], {'fields': ['partner_id']})[0]['partner_id'][0]
body = '<h3>' + html.escape(marker) + '</h3>'
body += '<p>Publicado en Desarrollo y Cerro El Plomo: cálculo CLP/USD visible antes de costear, ingreso en pesos o dólares con conversión diaria, botón Volver al estado anterior para provisiones validadas o costeadas sin asiento, y selección de las cuentas analíticas existentes desde la provisión. Se conservan los importes costeados y los asientos contabilizados.</p>'
body += '<p>Las cuentas creadas deben estar vinculadas a sus maestros. La inspección encontró sin relación la cuenta del embarque en Desarrollo y la de temporada en Cerro. Se solicitó identificar las cuentas correctas; no se asignaron por coincidencia de nombre. El ticket sigue en espera de esa definición.</p>'
body += '<p>Pasaron diez pruebas en cada copia privada y el flujo real de validar, costear, corregir y contabilizar con asiento balanceado y tres planes analíticos en ambos destinos. Publicado el mismo paquete con respaldo, bloqueo compartido y conservación de datos. Las muestras de prueba se descartaron.</p>'
body += '<p>Paquete ' + html.escape(args.commit) + '. <a href="https://github.com/fjcaroe/tracker-steps/blob/codex/ambientes-canonicos-reparacion/docs/T82_IMPLEMENTACION_2026-10-14.rst">Acta técnica</a>.</p>'
old = rpc('mail.message', 'search_read', [[('model', '=', 'helpdesk.ticket'), ('res_id', '=', 82), ('body', 'ilike', marker)]], {'fields': ['id']})
message = old[0]['id'] if old else rpc('mail.message', 'create', [{'model': 'helpdesk.ticket', 'res_id': 82, 'message_type': 'comment', 'subtype_id': note, 'author_id': author, 'body': body, 'partner_ids': [(5, 0, 0)]}])
saved = rpc('mail.message', 'read', [[message]], {'fields': ['subtype_id', 'notification_ids']})[0]
assert saved['subtype_id'][0] == note and not saved['notification_ids']
context = {'tracking_disable': True, 'mail_notrack': True, 'mail_create_nosubscribe': True, 'mail_auto_subscribe_no_notify': True}
rpc('helpdesk.ticket', 'write', [[82], {'stage_id': 6}], {'context': context})
assert rpc('helpdesk.ticket', 'read', [[82]], {'fields': ['stage_id']})[0]['stage_id'][0] == 6
print('TICKET_DELIVERY_OK 82 note', message, 'stage=waiting_account_identity notifications=0')
