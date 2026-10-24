import json
import re
import sys
import xmlrpc.client
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
c = json.loads((Path.home() / '.odoo' / 'helpdesk_api.json').read_text(encoding='utf-8'))
u = 'https://soporte.stepsapp.cl'
uid = xmlrpc.client.ServerProxy(f'{u}/xmlrpc/2/common').authenticate(c['db'], c['username'], c['api_key'], {})
m = xmlrpc.client.ServerProxy(f'{u}/xmlrpc/2/object')
for ticket_id in [16,22,27,28,30,35,38,39,40]:
    mids = m.execute_kw(c['db'], uid, c['api_key'], 'helpdesk.ticket', 'read', [[ticket_id]],
        {'fields': ['message_ids']})[0]['message_ids']
    messages = m.execute_kw(c['db'], uid, c['api_key'], 'mail.message', 'read', [mids],
        {'fields': ['body', 'subtype_id', 'message_type', 'author_id', 'date']})
    for x in sorted(messages, key=lambda r: r['date']):
        body = x['body'] or ''
        if x['subtype_id'][0] != 2 or 'IA-EVIDENCIA' not in body:
            continue
        escaped = bool(re.search(r'&lt;/?(?:p|br|ul|li|h[1-6])\b', body, re.I))
        short = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', body))[:100]
        print(f"T{ticket_id} {x['id']} {x['date']} len={len(body)} escaped={escaped} {short}")
