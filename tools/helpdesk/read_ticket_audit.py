"""Read current helpdesk requests to private artifacts without changing tickets."""
import argparse
import json
from pathlib import Path
import xmlrpc.client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--open-only', action='store_true', help='All unresolved tickets, highest priority first; oldest first within a priority')
    parser.add_argument('--ticket', type=int, action='append', help='Read specific tickets, including solved tickets with recent replies')
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

    assert not (args.open_only and args.ticket), 'Choose unresolved tickets or explicit ticket IDs'
    domain = [('id', 'in', args.ticket)] if args.ticket else [('stage_id', 'not in', [4, 5])] if args.open_only else []
    options = {
        'fields': ['id', 'name', 'description', 'stage_id', 'priority', 'create_date', 'write_date'],
        'order': 'priority desc, create_date asc, id asc' if args.open_only else 'write_date desc',
    }
    if not (args.open_only or args.ticket):
        options['limit'] = 70
    tickets = call('helpdesk.ticket', 'search_read', [domain], options)
    relevant = tickets if args.open_only or args.ticket else [t for t in tickets if any(w in (t['name'] + ' ' + (t['description'] or '')).lower() for w in ['packing', 'productor', 'export', 'versi', 'maestro', 'tabla', 'studio'])]
    for ticket in relevant:
        ticket['messages'] = call('mail.message', 'search_read', [[('model', '=', 'helpdesk.ticket'), ('res_id', '=', ticket['id'])]], {'fields': ['id', 'date', 'body', 'message_type', 'attachment_ids'], 'order': 'date desc', 'limit': 20})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(relevant, ensure_ascii=False, indent=2), encoding='utf-8')
    print('TICKET_AUDIT_SAVED count=' + str(len(relevant)) + ' path=' + str(args.output))
    for ticket in relevant:
        print(json.dumps({k: ticket[k] for k in ('id', 'name', 'stage_id', 'priority', 'create_date', 'write_date')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
