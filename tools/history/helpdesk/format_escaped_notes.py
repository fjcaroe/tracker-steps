"""Format two malformed historical Helpdesk notes without changing their words."""
import argparse
import html
import json
import re
import sys
import xmlrpc.client
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
parser = argparse.ArgumentParser()
parser.add_argument('--post', action='store_true')
args = parser.parse_args()
config = json.loads((Path.home() / '.odoo' / 'helpdesk_api.json').read_text(encoding='utf-8'))
url = 'https://soporte.stepsapp.cl'
uid = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common').authenticate(
    config['db'], config['username'], config['api_key'], {})
models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
messages = models.execute_kw(config['db'], uid, config['api_key'], 'mail.message', 'read',
    [[8803, 8810]], {'fields': ['body', 'model', 'res_id', 'subtype_id', 'date']})
backup = Path(__file__).with_name('escaped_notes_backup.json')
if not backup.exists():
    backup.write_text(json.dumps(messages, ensure_ascii=False, indent=2), encoding='utf-8')

def format_body(raw):
    decoded = html.unescape(raw)
    decoded = re.sub(r'</?p\s*/?>', '', decoded, flags=re.I)
    assert not re.search(r'<(?!br\s*/?>)[^>]+>', decoded, flags=re.I), 'Unexpected HTML'
    lines = [line.strip() for line in re.split(r'<br\s*/?>', decoded, flags=re.I)]
    out = []
    for line in lines:
        if not line:
            continue
        clean = html.escape(line, quote=False)
        if not out:
            out.append(f'<h3>{clean}</h3>')
        elif (line.isupper() and len(line) <= 110 and not line.startswith('-')):
            out.append(f'<h4>{clean}</h4>')
        elif re.match(r'^(?:\d+(?:-\d+)?[.)]|-)\s*', line):
            out.append(f'<p class="ms-3">{clean}</p>')
        else:
            out.append(f'<p>{clean}</p>')
    return '\n'.join(out)

for message in messages:
    expected_ticket = {8803: 38, 8810: 40}[message['id']]
    assert message['model'] == 'helpdesk.ticket' and message['res_id'] == expected_ticket
    assert message['subtype_id'][0] == 2
    assert '&lt;br' in message['body']
    formatted = format_body(message['body'])
    source_words = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html.unescape(message['body']))).strip()
    output_words = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html.unescape(formatted))).strip()
    assert source_words == output_words, 'Text changed during formatting'
    assert '⟦IA-EVIDENCIA⟧' in formatted
    assert '&lt;br' not in formatted
    print(f"T{expected_ticket} message={message['id']} old={len(message['body'])} new={len(formatted)} blocks={formatted.count('<p') + formatted.count('<h')}")
    print(formatted[:700])
    if args.post:
        models.execute_kw(config['db'], uid, config['api_key'], 'mail.message', 'write',
            [[message['id']], {'body': formatted}])
        stored = models.execute_kw(config['db'], uid, config['api_key'], 'mail.message', 'read',
            [[message['id']]], {'fields': ['body', 'res_id', 'date']})[0]
        assert stored['res_id'] == expected_ticket and stored['date'] == message['date']
        assert '&lt;br' not in stored['body'] and '<h3>' in stored['body']
        print('VERIFIED', message['id'])
