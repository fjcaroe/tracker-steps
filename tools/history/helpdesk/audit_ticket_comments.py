import json
import re
import sys
import xmlrpc.client
from pathlib import Path

config = json.loads((Path.home() / '.odoo' / 'helpdesk_api.json').read_text(encoding='utf-8'))
sys.stdout.reconfigure(encoding='utf-8')
url = 'https://soporte.stepsapp.cl'
common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
uid = common.authenticate(config['db'], config['username'], config['api_key'], {})
models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
ids = [16, 22, 27, 28, 30, 35, 38, 39, 40]
for ticket_id in ids:
    tickets = models.execute_kw(config['db'], uid, config['api_key'], 'helpdesk.ticket', 'read', [[ticket_id]], {'fields': ['name', 'message_ids']})
    if not tickets:
        continue
    ticket = tickets[0]
    messages = models.execute_kw(config['db'], uid, config['api_key'], 'mail.message', 'search_read',
        [[('model', '=', 'helpdesk.ticket'), ('res_id', '=', ticket_id)]],
        {'fields': ['body', 'date', 'author_id', 'message_type', 'subtype_id'], 'order': 'date desc', 'limit': 12})
    print(f"T{ticket_id} {ticket['name']}")
    for message in sorted(messages, key=lambda item: item['date']):
        body = message.get('body') or ''
        if message['message_type'] not in ('comment', 'email') or not body.strip():
            continue
        flags = []
        if re.search(r'&lt;/?(?:p|br|ul|ol|li|h[1-6])\b', body, re.I):
            flags.append('ESCAPED_HTML')
        if '<p' not in body.lower() and '<div' not in body.lower() and '<ul' not in body.lower():
            flags.append('NO_LAYOUT')
        if '\n' in re.sub(r'<[^>]+>', '', body):
            flags.append('NEWLINES')
        flat = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', body))
        print(f"  {message['id']} {message['date']} {message['author_id']} {','.join(flags) or 'OK'} {flat[:200]}")
