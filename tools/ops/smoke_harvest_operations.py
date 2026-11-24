"""Prove Harvest delivery and OT lifecycle only through a certified private copy.

The copy's existing native OT receives a single QA delivery. Its mobile status
then advances through closed/reviewed/sent, while its ERP state remains in. The
original customer databases are never reachable through this client.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import uuid

from harvest_web_policy import require_copy_sync_certificate
from smoke_harvest_android_sync import ReviewClient, positive_id, require_success, review_origin


class OperationsClient(ReviewClient):
    allowed_requests = (*ReviewClient.allowed_requests, ('POST', '/api/harvest/orders/transition'))


def validate_operations_policy(origin, stage_name, proof, policy):
    origin = review_origin(origin)
    frontend = proof['harvest_web']
    environment = policy['environment']
    assert environment in ('development', 'cerro', 'qa-cerro')
    assert frontend['version'] == '0.0.8'
    assert re.fullmatch('[a-f0-9]{40}', proof['commit'])
    assert re.fullmatch('[a-f0-9]{64}', proof['release_sha256'])
    assert stage_name == 'management_' + environment + '_t236237_' + proof['commit'][:8]
    assert proof['database'] == 'MANAGEMENT_QA_' + environment.upper() + '_t236237_' + proof['commit'][:8]
    assert proof['feature'] == 'harvest-app' and proof['business_preserved'] is True
    require_copy_sync_certificate(frontend, environment, stage_name, proof)
    assert policy['database'] == proof['database']
    assert policy['web_commit'] == frontend['commit']
    assert policy['read_only'] is False and policy['copy_sync_allowed'] is True
    assert policy['sync_origin'] == origin
    assert positive_id(policy['user_id']) and policy['user_id'] > 1
    assert positive_id(policy['company_id'])


def exercise_operations(client, policy, run_uuid=None):
    status, session = client.request('GET', '/api/harvest/session')
    require_success(status, session, 'Native session')
    assert session.get('connected') is True
    status, bootstrap = client.request('GET', '/api/harvest/bootstrap')
    require_success(status, bootstrap, 'Native bootstrap')
    for data in (session, bootstrap):
        assert data['user']['id'] == policy['user_id'], 'The proxy profile changed'
        assert data['company']['id'] == policy['company_id'], 'The proxy company changed'
    scope = bootstrap['scope']
    assert isinstance(scope, str) and re.fullmatch('[a-f0-9]{64}', scope) and session['scope'] == scope
    orders = [row for row in bootstrap['orders'] if positive_id(row.get('odoo_id'))
              and row.get('status') == 'En proceso' and row.get('erp_state') == 'in'
              and row.get('can_transition') is True]
    workers = [row for row in bootstrap['workers'] if positive_id(row.get('id'))]
    assert orders and workers, 'The copy company needs an existing writable OT in ERP in/mobile progress and an accessible worker'
    order = orders[0]
    run_uuid = run_uuid or 'QA-HARVEST-OPS-' + uuid.uuid4().hex
    assert re.fullmatch(r'QA-HARVEST-OPS-[a-f0-9]{32}', run_uuid)
    record = {'client_uuid': run_uuid, 'worker_id': workers[0]['id'],
        'work_order': {'odoo_id': order['odoo_id']}, 'tarja': 'QA-OPS-' + run_uuid[-12:],
        'row': 'QA-OPERATIONS', 'boxes': 1, 'kilos': 1,
        'event_datetime': datetime.now(timezone.utc).isoformat()}
    altered = ('f' if scope[0] != 'f' else 'e') + scope[1:]
    status, rejected = client.request('POST', '/api/harvest/sync', {'scope': altered, 'records': [record]})
    assert status == 409 and rejected.get('ok') is False, 'A changed scope must be rejected before upload'

    def upload(delivery, *, duplicate, native_id=None):
        status, result = client.request('POST', '/api/harvest/sync', {'scope': scope, 'records': [delivery]})
        require_success(status, result, 'Copy delivery')
        results = result.get('results')
        assert isinstance(results, list) and len(results) == 1
        line = results[0]
        assert line.get('ok') is True and line.get('duplicate') is duplicate
        assert line.get('client_uuid') == delivery['client_uuid'] and positive_id(line.get('id'))
        assert line.get('work_order_id') == order['odoo_id'], 'Delivery belongs to another native OT'
        if native_id is not None:
            assert line['id'] == native_id, 'Retry created or resolved a different native line'
        return line['id']

    native_id = upload(record, duplicate=False)
    upload(record, duplicate=True, native_id=native_id)
    payload = {'scope': scope, 'work_order': {'odoo_id': order['odoo_id']},
               'delivery_uuids': [run_uuid], 'action': 'close'}
    status, rejected = client.request('POST', '/api/harvest/orders/transition', dict(payload, scope=altered))
    assert status == 409 and rejected.get('ok') is False, 'A transition cannot bypass the original context'
    status, rejected = client.request('POST', '/api/harvest/orders/transition',
        dict(payload, delivery_uuids=[run_uuid, 'QA-MISSING-' + uuid.uuid4().hex]))
    assert status == 422 and rejected.get('ok') is False, 'An unconfirmed delivery must prevent closing'

    def transition(action, expected):
        status, result = client.request('POST', '/api/harvest/orders/transition', dict(payload, action=action))
        require_success(status, result, 'Copy ' + action)
        assert result.get('scope') == scope
        assert result.get('confirmed_delivery_uuids') == [run_uuid]
        state = result['order']
        assert state['odoo_id'] == order['odoo_id'] and state['status'] == expected
        assert state['erp_state'] == 'in', 'The mobile lifecycle must preserve ERP approval/costing'
        return state

    closed = transition('close', 'Cerrada')
    retried = transition('close', 'Cerrada')
    assert retried.get('state_changed_at') == closed.get('state_changed_at'), 'A retry must not add another lifecycle event'
    upload(record, duplicate=True, native_id=native_id)
    status, rejected = client.request('POST', '/api/harvest/sync',
        {'scope': scope, 'records': [dict(record, client_uuid=run_uuid + '-AFTER-CLOSE')]})
    assert status == 200 and rejected.get('ok') is False
    assert len(rejected.get('results', [])) == 1 and rejected['results'][0].get('ok') is False
    transition('review', 'Revisada')
    transition('send', 'Enviada')
    status, refreshed = client.request('GET', '/api/harvest/bootstrap')
    require_success(status, refreshed, 'Native refresh')
    assert refreshed.get('scope') == scope
    confirmed = next(row for row in refreshed['orders'] if row.get('odoo_id') == order['odoo_id'])
    assert confirmed['status'] == 'Enviada' and confirmed['erp_state'] == 'in'
    return {'run_uuid': run_uuid, 'native_order_id': order['odoo_id'], 'native_line_id': native_id,
        'native_context': True, 'scope_rejected_before_write': True, 'native_copy_sync': True,
        'sync_idempotency': True, 'unconfirmed_delivery_blocks_close': True, 'ot_close': True,
        'ot_review': True, 'ot_send_confirmation': True, 'close_retry_idempotency': True,
        'new_delivery_rejected_after_close': True, 'erp_state_preserved': True,
        'new_lines': 1, 'existing_relations_only': True, 'credentials_or_session_ids_supplied': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--stage', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    origin = review_origin(args.url)
    stage = args.stage
    assert stage.resolve() == stage and stage.parent == Path('/opt/steps-validation') and not stage.is_symlink()
    proof = json.loads((stage/'qa_passed.json').read_text())
    policy = json.loads((stage/'harvest-review-policy.json').read_text())
    validate_operations_policy(origin, stage.name, proof, policy)
    output = args.output
    assert output.is_absolute() and output.resolve() == output and not output.exists()
    assert not any((parent/'.git').exists() for parent in output.parents), 'Keep evidence outside checkouts'
    evidence = exercise_operations(OperationsClient(origin), policy)
    evidence.update({'feature': proof['feature'], 'stage': stage.name, 'database': proof['database'],
        'web_commit': proof['harvest_web']['commit'], 'backend_commit': proof['commit'],
        'backend_sha256': proof['release_sha256'], 'created_at': datetime.now(timezone.utc).isoformat()})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    output.chmod(0o600)
    print('HARVEST_OPERATIONS_COPY_OK ' + json.dumps(evidence, sort_keys=True))


if __name__ == '__main__':
    main()
