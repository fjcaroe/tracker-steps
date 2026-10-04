import json
import re
import xmlrpc.client
from pathlib import Path

c = json.loads((Path.home() / '.odoo' / 'helpdesk_api.json').read_text(encoding='utf-8'))
url = 'https://soporte.stepsapp.cl'
uid = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common').authenticate(c['db'], c['username'], c['api_key'], {})
models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
for mid in (8803, 8810):
    message = models.execute_kw(c['db'], uid, c['api_key'], 'mail.message', 'read',
        [[mid]], {'fields': ['body', 'res_id', 'date']})[0]
    body = message['body']
    revised, n = re.subn(r'^<h3>(.*?)</h3>', r'<p><strong>\1</strong></p>', body, count=1, flags=re.S)
    assert n == 1 and body.count('<h3>') == 1 and '<h3>' not in revised
    models.execute_kw(c['db'], uid, c['api_key'], 'mail.message', 'write',
        [[mid], {'body': revised}])
    stored = models.execute_kw(c['db'], uid, c['api_key'], 'mail.message', 'read',
        [[mid]], {'fields': ['body', 'res_id', 'date']})[0]
    assert stored['body'] == revised and stored['date'] == message['date'] and stored['res_id'] == message['res_id']
    print('REFINED', mid, message['res_id'])
