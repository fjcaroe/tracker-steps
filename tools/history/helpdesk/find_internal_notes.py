import json
import sys
import xmlrpc.client
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
c = json.loads((Path.home() / '.odoo' / 'helpdesk_api.json').read_text(encoding='utf-8'))
u = 'https://soporte.stepsapp.cl'
uid = xmlrpc.client.ServerProxy(f'{u}/xmlrpc/2/common').authenticate(c['db'], c['username'], c['api_key'], {})
m = xmlrpc.client.ServerProxy(f'{u}/xmlrpc/2/object')
fields = m.execute_kw(c['db'], uid, c['api_key'], 'helpdesk.ticket', 'fields_get', [],
    {'attributes': ['string', 'type', 'relation']})
for key, meta in fields.items():
    if any(s in key.lower() for s in ('note', 'comment', 'message')):
        print(key, meta)
model_names = m.execute_kw(c['db'], uid, c['api_key'], 'ir.model', 'search_read',
    [[('model', 'ilike', 'helpdesk'), ('name', 'ilike', 'note')]],
    {'fields': ['model', 'name'], 'limit': 30})
print('note_models', model_names)
for ticket_id in [16,22,27,28,30,35,38,39,40]:
    ticket = m.execute_kw(c['db'], uid, c['api_key'], 'helpdesk.ticket', 'read', [[ticket_id]],
        {'fields': ['message_ids', 'website_message_ids']})[0]
    for field in ('message_ids', 'website_message_ids'):
        mids = ticket[field]
        messages = m.execute_kw(c['db'], uid, c['api_key'], 'mail.message', 'read', [mids],
            {'fields': ['body', 'subtype_id', 'message_type', 'author_id']}) if mids else []
        bad = [(x['id'], x['message_type'], x['subtype_id'], (x['body'] or '')[:90])
               for x in messages if 'IA-EVIDENCIA' in (x['body'] or '') or 'IA&#' in (x['body'] or '') or 'IA-' in (x['body'] or '')]
        print(ticket_id, field, len(mids), bad)
