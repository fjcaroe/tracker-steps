"""Close T244/T245 silently only after their three verified deployments."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import xmlrpc.client


def verify_evidence(root):
    expected = {'step_harvest_launcher': '18.0.1.7.0', 'step_cosecha_operations': '18.0.1.2.0'}
    identity = None
    for target in ('development', 'qa-cerro', 'cerro'):
        qa = json.loads((root / (target + '-qa.json')).read_text())
        web = json.loads((root / (target + '-web.json')).read_text())
        copy = json.loads((root / (target + '-copy-review.json')).read_text())
        live = json.loads((root / (target + '-live-review.json')).read_text())
        operations = json.loads((root / (target + '-operations-smoke.json')).read_text())
        assert qa['environment'] == web['environment'] == live['environment'] == target
        assert qa['business_preserved'] is True and qa['backend_versions'] == expected
        assert qa['commit'] == web['backend_commit'] == copy['backend_commit'] == live['backend_commit'] == operations['backend_commit']
        assert qa['release_sha256'] == copy['backend_sha256'] == operations['backend_sha256']
        assert web['web_commit'] == copy['web_commit'] == live['web_commit'] == operations['web_commit']
        assert web['backup'] and copy['reviewed'] is True and live['reviewed'] is True
        assert live['version'] == '0.0.12' and live['server_writes'] is False
        if target in ('cerro', 'qa-cerro'):
            assert live['company_id'] == copy['operation_company_id'] == 1
        for key in ('ot_native_fields', 'pass_required', 'ot_work_hours', 'day_allocation'):
            assert operations[key] is True and copy[key] is True and live[key] is True
        assert operations['native_cost_hours'] is True and copy['native_cost_hours'] is True
        assert all(copy[key] is True for key in ('client_close_with_hours', 'client_approval_send', 'client_native_fields', 'client_reload_preserved'))
        counts = re.findall(r'0 failed, 0 error\(s\) of (\d+) tests when loading database',
                            (root / (target + '-qa.log')).read_text())
        assert counts and int(counts[-1]) >= 91
        current = (qa['commit'], qa['release_sha256'], web['web_commit'], web['served'])
        assert identity is None or current == identity
        identity = current
    pair = json.loads((root / 'pair.json').read_text())
    for module, version in expected.items():
        assert pair['cerro'][module]['version'] == pair['qa-cerro'][module]['version'] == version
        assert pair['cerro'][module]['sha256'] == pair['qa-cerro'][module]['sha256']
    isolation = (root / 'isolation.log').read_text()
    assert all(marker in isolation for marker in ('CUSTOMER_QA_VERIFY_OK', 'CUSTOMER_QA_EGRESS_BLOCKED', 'CUSTOMER_QA_SOURCE_DB_DENIED'))
    return identity[:3]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    root = args.evidence.resolve()
    assert not root.is_relative_to(Path(__file__).resolve().parents[2])
    package = verify_evidence(root)
    config = json.loads((Path.home() / '.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
    url = 'https://soporte.stepsapp.cl'
    uid = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/common').authenticate(config['db'], config['username'], config['api_key'], {})
    assert uid
    rpc = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/object')
    context = {'tracking_disable': True, 'mail_notrack': True, 'mail_create_nosubscribe': True,
        'mail_auto_subscribe_no_notify': True, 'mail_notify_force_send': False}

    def call(model, method, values, **kwargs):
        return rpc.execute_kw(config['db'], uid, config['api_key'], model, method, values,
                              {'context': context, **kwargs})

    model = call('ir.model', 'search', [[('model', '=', 'helpdesk.ticket')]])
    assert not call('base.automation', 'search_count', [[('model_id', 'in', model), ('active', '=', True)]])
    stage = call('helpdesk.stage', 'read', [[4]], fields=['fold', 'team_ids'])[0]
    assert stage['fold'] and 2 in stage['team_ids']
    plans = []
    for ticket, reviewed in ((244, 10692), (245, 10696)):
        current = call('helpdesk.ticket', 'read', [[ticket]], fields=['name', 'stage_id', 'team_id', 'sla_ids', 'sla_status_ids'])[0]
        assert current['stage_id'][0] in (1, 2, 4) and current['team_id'][0] == 2
        assert not current['sla_ids'] and not current['sla_status_ids']
        domain = [('model', '=', 'helpdesk.ticket'), ('res_id', '=', ticket)]
        messages = call('mail.message', 'search_read', [domain], fields=['id'], order='id')
        assert max(row['id'] for row in messages) == reviewed, 'Read newer ticket responses before closure'
        plans.append((ticket, current, domain, messages))
    results = []
    for ticket, before, domain, messages in plans:
        mail_domain = [('mail_message_id.model', '=', 'helpdesk.ticket'), ('mail_message_id.res_id', '=', ticket)]
        notifications = {model: set(call(model, 'search', [mail_domain])) for model in ('mail.notification', 'mail.mail')}
        if args.apply and before['stage_id'][0] != 4:
            call('helpdesk.ticket', 'write', [[ticket], {'stage_id': 4}])
        after = call('helpdesk.ticket', 'read', [[ticket]], fields=['stage_id'])[0]
        assert not args.apply or after['stage_id'][0] == 4
        assert messages == call('mail.message', 'search_read', [domain], fields=['id'], order='id')
        assert all(set(call(model, 'search', [mail_domain])) == ids for model, ids in notifications.items()), 'Unexpected ticket email or notification'
        results.append({'ticket': ticket, 'before': before['stage_id'], 'after': after['stage_id'], 'comment_posted': False})
    proof = {'package': package, 'applied': args.apply, 'results': results,
             'verified_at': datetime.now(timezone.utc).isoformat()}
    (root / 'ticket-closure.json').write_text(json.dumps(proof, indent=2))
    print('HARVEST_HOURS_TICKETS_VERIFIED ' + json.dumps({'applied': args.apply, 'results': results}))


if __name__ == '__main__':
    main()
