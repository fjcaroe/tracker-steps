"""Read current helpdesk requests to private artifacts without changing tickets."""
import argparse
import json
from pathlib import Path
import xmlrpc.client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    assert not args.output.resolve().is_relative_to(root)
    config = json.loads((Path.home() / '.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
    url = 'https://soporte.stepsapp.cl'
    common = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/common')
    uid = common.authenticate(config['db'], config['username'], config['api_key'], {})
    assert uid, 'Authentication failed'
    rpc = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/object')

    def call(model, method, args, kwargs=None):
        return rpc.execute_kw(config['db'], uid, config['api_key'], model, method, args, kwargs or {})

    tickets = call('helpdesk.ticket', 'search_read', [[]], {'fields': ['id', 'name', 'description', 'stage_id', 'write_date'], 'order': 'write_date desc', 'limit': 70})
    relevant = [t for t in tickets if any(w in (t['name'] + ' ' + (t['description'] or '')).lower() for w in ['packing', 'productor', 'export', 'versi', 'maestro', 'tabla', 'studio'])]
    for ticket in relevant:
        ticket['messages'] = call('mail.message', 'search_read', [[('model', '=', 'helpdesk.ticket'), ('res_id', '=', ticket['id'])]], {'fields': ['id', 'date', 'body', 'message_type'], 'order': 'date desc', 'limit': 20})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(relevant, ensure_ascii=False, indent=2), encoding='utf-8')
    print('TICKET_AUDIT_SAVED count=' + str(len(relevant)) + ' path=' + str(args.output))
    for ticket in relevant:
        print(json.dumps({k: ticket[k] for k in ('id', 'name', 'stage_id', 'write_date')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
