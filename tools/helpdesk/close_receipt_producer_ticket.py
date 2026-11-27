"""Close T246 silently after the identical package and both forms pass in all targets."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import xmlrpc.client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    parser.add_argument('--reviewed-message', type=int, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    root = args.evidence.resolve()
    assert not root.is_relative_to(Path(__file__).resolve().parents[2])
    release = json.loads((root / 'release.json').read_text())
    assert release['versions'] == {'step_packing_producer_change': '18.0.1.1.0'}
    identity = None
    for target in ('development', 'cerro', 'qa-cerro'):
        qa = json.loads((root / (target + '-qa.json')).read_text())
        deployment = json.loads((root / (target + '-deployment.json')).read_text())
        live = json.loads((root / (target + '-live-review.json')).read_text())
        assert qa['commit'] == deployment['commit'] == release['commit']
        assert qa['release_sha256'] == deployment['sha256']
        assert qa['environment'] == target and qa['business_preserved'] is True
        assert live['ticket'] == 246 and live['no_business_writes'] is True and not live['errors']
        assert {form['kind'] for form in live['forms'] if form['wizard']} == {'receipt', 'tag'}
        assert live['user'] > 1
        counts = re.findall(r'0 failed, 0 error\(s\) of (\d+) tests when loading database',
                            (root / (target + '-qa.log')).read_text())
        assert counts and int(counts[-1]) >= 11
        verification = (root / (target + '-live-verification.log')).read_text()
        assert 'MANAGEMENT_REGISTRY_OK' in verification and '"receipt_and_c_tag": true' in verification
        current = (qa['commit'], qa['release_sha256'])
        assert identity is None or current == identity
        identity = current
    pair = json.loads((root / 'pair.json').read_text())
    assert pair['cerro']['step_packing_producer_change']['sha256'] == pair['qa-cerro']['step_packing_producer_change']['sha256']
    isolation = (root / 'isolation.log').read_text()
    assert all(marker in isolation for marker in ('CUSTOMER_QA_VERIFY_OK', 'CUSTOMER_QA_EGRESS_BLOCKED', 'CUSTOMER_QA_SOURCE_DB_DENIED'))
    config = json.loads((Path.home() / '.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
    url = 'https://soporte.stepsapp.cl'
    uid = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/common').authenticate(config['db'], config['username'], config['api_key'], {})
    assert uid
    rpc = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/object')
    context = {'tracking_disable': True, 'mail_notrack': True, 'mail_create_nosubscribe': True,
        'mail_auto_subscribe_no_notify': True, 'mail_notify_force_send': False}

    def call(model, method, values, **kwargs):
        return rpc.execute_kw(config['db'], uid, config['api_key'], model, method, values, {'context': context, **kwargs})

    model = call('ir.model', 'search', [[('model', '=', 'helpdesk.ticket')]])
    assert not call('base.automation', 'search_count', [[('model_id', 'in', model), ('active', '=', True)]])
    stage = call('helpdesk.stage', 'read', [[4]], fields=['fold', 'team_ids'])[0]
    assert stage['fold'] and 2 in stage['team_ids']
    ticket = call('helpdesk.ticket', 'read', [[246]], fields=['stage_id', 'team_id', 'sla_ids', 'sla_status_ids'])[0]
    assert ticket['team_id'][0] == 2 and ticket['stage_id'][0] in (1, 2, 4)
    assert not ticket['sla_ids'] and not ticket['sla_status_ids']
    domain = [('model', '=', 'helpdesk.ticket'), ('res_id', '=', 246)]
    messages = call('mail.message', 'search_read', [domain], fields=['id'], order='id')
    assert max(row['id'] for row in messages) == args.reviewed_message, 'Review newer replies before closure'
    mail_domain = [('mail_message_id.model', '=', 'helpdesk.ticket'), ('mail_message_id.res_id', '=', 246)]
    notifications = {model: set(call(model, 'search', [mail_domain])) for model in ('mail.notification', 'mail.mail')}
    if args.apply and ticket['stage_id'][0] != 4:
        call('helpdesk.ticket', 'write', [[246], {'stage_id': 4}])
    after = call('helpdesk.ticket', 'read', [[246]], fields=['stage_id'])[0]
    assert not args.apply or after['stage_id'][0] == 4
    assert messages == call('mail.message', 'search_read', [domain], fields=['id'], order='id')
    assert all(set(call(model, 'search', [mail_domain])) == ids for model, ids in notifications.items())
    result = {'ticket': 246, 'applied': args.apply, 'before': ticket['stage_id'], 'after': after['stage_id'],
              'package': identity, 'messages_unchanged': True, 'notifications_unchanged': True,
              'verified_at': datetime.now(timezone.utc).isoformat()}
    (root / 'ticket-closure.json').write_text(json.dumps(result, indent=2))
    print('T246_CLOSURE_OK ' + json.dumps(result))


if __name__ == '__main__':
    main()
