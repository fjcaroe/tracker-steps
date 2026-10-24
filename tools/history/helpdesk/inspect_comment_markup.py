import json
import re
import sys
import xmlrpc.client
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
config = json.loads((Path.home() / '.odoo' / 'helpdesk_api.json').read_text(encoding='utf-8'))
url = 'https://soporte.stepsapp.cl'
uid = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common').authenticate(
    config['db'], config['username'], config['api_key'], {})
models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
ids = [8803, 8810, 8820]
messages = models.execute_kw(config['db'], uid, config['api_key'], 'mail.message', 'read', [ids],
    {'fields': ['body', 'res_id', 'author_id']})
for message in messages:
    body = message.get('body') or ''
    tags = re.findall(r'</?([a-zA-Z][\w:-]*)\b', body)
    print(message['id'], 'ticket', message['res_id'], 'length', len(body), 'tags', tags[:30])
    print(repr(body[:1200]))
