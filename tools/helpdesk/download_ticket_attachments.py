"""Download requested ticket attachments to private artifacts without changes."""
import argparse
import base64
import json
from pathlib import Path
import re
import xmlrpc.client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ticket', type=int, required=True)
    parser.add_argument('--attachment', type=int, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[2]
    assert not args.output.resolve().is_relative_to(repository)
    config = json.loads((Path.home() / '.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
    url = 'https://soporte.stepsapp.cl'
    uid = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/common').authenticate(
        config['db'], config['username'], config['api_key'], {})
    assert uid, 'Authentication failed'
    rpc = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/object')

    def call(model, method, values, kwargs=None):
        return rpc.execute_kw(config['db'], uid, config['api_key'], model, method, values, kwargs or {})

    messages = call('mail.message', 'search_read', [[
        ('model', '=', 'helpdesk.ticket'), ('res_id', '=', args.ticket)]],
        {'fields': ['attachment_ids']})
    related = {ident for message in messages for ident in message['attachment_ids']}
    assert set(args.attachment).issubset(related), 'Attachment is not linked to this ticket'
    args.output.mkdir(parents=True, exist_ok=True)
    for row in call('ir.attachment', 'read', [sorted(set(args.attachment))],
                    {'fields': ['name', 'mimetype', 'datas']}):
        filename = re.sub(r'[^\w. -]', '_', Path(row['name']).name)
        path = args.output / (str(row['id']) + '-' + filename)
        data = base64.b64decode(row['datas'])
        if path.exists():
            assert path.read_bytes() == data, 'Existing artifact differs'
        else:
            path.write_bytes(data)
        print(json.dumps({'id': row['id'], 'name': row['name'], 'type': row['mimetype'],
                          'bytes': len(data), 'path': str(path)}, ensure_ascii=True))


if __name__ == '__main__':
    main()
