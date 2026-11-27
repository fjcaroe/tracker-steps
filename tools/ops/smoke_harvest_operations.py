"""Prove Harvest delivery and OT lifecycle only through a certified private copy.

Harvest .9 creates a QA OT from existing masters, reopens before sending,
approves natively and sends its complete declared queue with atomic retries.
The .8 historical mode remains available for its original archived evidence.
The original customer databases are never reachable through this client.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path
import re
import uuid

from harvest_web_policy import (OPERATIONS_VERSIONS, OPERATIONS_CASES, REVISED_OPERATIONS_VERSIONS,
                                WEIGHT_VERSIONS, require_copy_sync_certificate)
from smoke_harvest_android_sync import ReviewClient, positive_id, require_success, review_origin


MANIFEST_READ_PATH = '/web/dataset/call_kw/step.cosecha.tarja.registry.line/search_read'


class OperationsClient(ReviewClient):
    allowed_requests = (*ReviewClient.allowed_requests, ('POST', '/api/harvest/orders/transition'),
                        ('POST', MANIFEST_READ_PATH))


def read_native_manifest(client, order_id, fields=()):
    status, response = client.request('POST', MANIFEST_READ_PATH, {
        'jsonrpc': '2.0', 'method': 'call', 'id': 1,
        'params': {'model': 'step.cosecha.tarja.registry.line', 'method': 'search_read',
                   'args': [[['registry_id', '=', order_id], ['mobile_uid', '!=', False]]],
                   'kwargs': {'fields': ['id', 'mobile_uid', 'registry_id', *fields], 'order': 'id'}}})
    assert status == 200 and not response.get('error') and isinstance(response.get('result'), list), \
        'The private copy could not read the native delivery manifest'
    rows = response['result']
    assert all(positive_id(row.get('id')) and isinstance(row.get('mobile_uid'), str)
               and row['mobile_uid'].strip() and isinstance(row.get('registry_id'), list) and row['registry_id']
               and row['registry_id'][0] == order_id for row in rows), 'The manifest contains another OT or invalid native identities'
    assert len({row['mobile_uid'] for row in rows}) == len(rows), 'The native delivery manifest contains repeated UUIDs'
    return rows


def validate_operations_policy(origin, stage_name, proof, policy):
    origin = review_origin(origin)
    frontend = policy['harvest_web']
    environment = policy['environment']
    assert environment in ('development', 'cerro', 'qa-cerro')
    assert frontend['version'] in OPERATIONS_VERSIONS
    assert re.fullmatch('[a-f0-9]{40}', proof['commit'])
    assert re.fullmatch('[a-f0-9]{64}', proof['release_sha256'])
    run_id = OPERATIONS_CASES[frontend['version']][0] + '_' + proof['commit'][:8]
    assert stage_name == 'management_' + environment + '_' + run_id
    assert proof['database'] == 'MANAGEMENT_QA_' + environment.upper() + '_' + run_id
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
    workers = {row['id']: row for row in bootstrap['workers'] if positive_id(row.get('id'))}
    crews = {row['id']: row for row in bootstrap.get('crews', []) if positive_id(row.get('id'))}
    candidates = [(order, workers[identifier]) for order in orders
                  for identifier in crews.get(order.get('crew_id'), {}).get('worker_ids', []) if identifier in workers]
    native_manifest = []
    if candidates:
        order, worker = candidates[0]
    else:
        historical = [row for row in bootstrap['orders'] if positive_id(row.get('odoo_id'))
                      and row.get('status') == 'En proceso' and row.get('erp_state') in ('apro', 'costo')
                      and row.get('can_transition') is True]
        order = None
        for candidate in historical:
            native_manifest = read_native_manifest(client, candidate['odoo_id'])
            if native_manifest:
                order = candidate
                break
        assert order, 'The copy needs a writable mobile OT in progress: ERP in with a native crew member, or ERP approved/costing with an existing mobile delivery manifest; prepare the missing fixture in the private copy UI'
    original_erp_state = order['erp_state']
    run_uuid = run_uuid or 'QA-HARVEST-OPS-' + uuid.uuid4().hex
    assert re.fullmatch(r'QA-HARVEST-OPS-[a-f0-9]{32}', run_uuid)
    record = {'client_uuid': native_manifest[0]['mobile_uid'],
              'work_order': {'odoo_id': order['odoo_id']}} if native_manifest else {
        'client_uuid': run_uuid, 'worker_id': worker['id'],
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

    native_id = upload(record, duplicate=bool(native_manifest),
                       native_id=native_manifest[0]['id'] if native_manifest else None)
    upload(record, duplicate=True, native_id=native_id)
    delivery_uuids = [row['mobile_uid'] for row in native_manifest] if native_manifest else [run_uuid]
    payload = {'scope': scope, 'work_order': {'odoo_id': order['odoo_id']},
               'delivery_uuids': delivery_uuids, 'action': 'close'}
    status, rejected = client.request('POST', '/api/harvest/orders/transition', dict(payload, scope=altered))
    assert status == 409 and rejected.get('ok') is False, 'A transition cannot bypass the original context'
    status, rejected = client.request('POST', '/api/harvest/orders/transition',
        dict(payload, delivery_uuids=[*delivery_uuids, 'QA-MISSING-' + uuid.uuid4().hex]))
    assert status == 422 and rejected.get('ok') is False, 'An unconfirmed delivery must prevent closing'

    def transition(action, expected):
        status, result = client.request('POST', '/api/harvest/orders/transition', dict(payload, action=action))
        require_success(status, result, 'Copy ' + action)
        assert result.get('scope') == scope
        assert result.get('confirmed_delivery_uuids') == delivery_uuids
        state = result['order']
        assert state['odoo_id'] == order['odoo_id'] and state['status'] == expected
        assert state['erp_state'] == original_erp_state, 'The mobile lifecycle must preserve ERP approval/costing'
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
    assert confirmed['status'] == 'Enviada' and confirmed['erp_state'] == original_erp_state
    return {'run_uuid': run_uuid, 'native_order_id': order['odoo_id'], 'native_line_id': native_id,
        'native_context': True, 'scope_rejected_before_write': True, 'native_copy_sync': True,
        'sync_idempotency': True, 'unconfirmed_delivery_blocks_close': True, 'ot_close': True,
        'ot_review': True, 'ot_send_confirmation': True, 'close_retry_idempotency': True,
        'new_delivery_rejected_after_close': True, 'erp_state_preserved': True,
        'native_order_id': order['odoo_id'], 'native_line_id': native_id,
        'new_lines': 0 if native_manifest else 1, 'existing_native_deliveries': len(native_manifest),
        'existing_relations_only': True, 'credentials_or_session_ids_supplied': False}


def exercise_revised_operations(client, policy, run_uuid=None):
    """Create a QA OT, reopen it, approve natively and send its full queue."""
    status, session = client.request('GET', '/api/harvest/session')
    require_success(status, session, 'Native session')
    assert session.get('connected') is True
    status, bootstrap = client.request('GET', '/api/harvest/bootstrap')
    require_success(status, bootstrap, 'Native bootstrap')
    for identity in (session, bootstrap):
        assert identity['user']['id'] == policy['user_id'] and identity['company']['id'] == policy['company_id']
    scope = bootstrap['scope']
    assert isinstance(scope, str) and re.fullmatch('[a-f0-9]{64}', scope) and session['scope'] == scope
    assert policy['user_id'] in {row['id'] for row in bootstrap['approvers']}, 'The existing profile must be a native approver'
    workers = {row['id'] for row in bootstrap['workers'] if positive_id(row.get('id'))}
    crew_candidates = [(row, member) for row in bootstrap['crews']
                       for member in row.get('worker_ids', []) if member in workers]
    farms = {row['id'] for row in bootstrap['farms'] if positive_id(row.get('id'))}
    varieties = {row['id'] for row in bootstrap['varieties'] if positive_id(row.get('id'))}
    centers = [row for row in bootstrap['cost_centers']
               if row.get('farm_id') in farms and row.get('variety_id') in varieties]
    assert crew_candidates and centers, 'The copy needs a native crew member and a coherent farm/variety/cost center before writes'
    crew, worker_id = crew_candidates[0]
    center = centers[0]
    run_uuid = run_uuid or 'QA-HARVEST-OPS-' + uuid.uuid4().hex
    assert re.fullmatch(r'QA-HARVEST-OPS-[a-f0-9]{32}', run_uuid)
    work_order = {'id': run_uuid + '-OT', 'client_uuid': run_uuid + '-OT', 'crew_id': crew['id'],
                  'farm_id': center['farm_id'], 'variety_id': center['variety_id'], 'cost_id': center['id'],
                  'approver_id': policy['user_id']}
    if center.get('cuarteles'):
        work_order['cuartel_id'] = center['cuarteles'][0]['id']
    first = {'client_uuid': run_uuid, 'worker_id': worker_id, 'work_order': work_order,
             'tarja': 'QA-OPS-' + run_uuid[-12:], 'row': 'QA-OPERATIONS', 'boxes': 1, 'kilos': 1,
             'event_datetime': datetime.now(timezone.utc).isoformat()}
    pending = dict(first, client_uuid=run_uuid + '-PENDING', tarja=first['tarja'] + '-PENDING')
    version = policy.get('harvest_web', {}).get('version')
    weights = version in WEIGHT_VERSIONS
    if weights:
        packaging = next((row for row in bootstrap['harvest_packagings'] if row['kg_per_box'] >= 0.01), None)
        assert packaging, 'Select an existing company with a Cosecha packaging and kilos per box'
        work_order.update(standard_weight=True, packaging_id=packaging['id'], kg_per_box=packaging['kg_per_box'])
        first['boxes'] = pending['boxes'] = 3
    altered = ('f' if scope[0] != 'f' else 'e') + scope[1:]
    status, rejected = client.request('POST', '/api/harvest/sync', {'scope': altered, 'records': [first]})
    assert status == 409 and rejected.get('ok') is False
    status, received = client.request('POST', '/api/harvest/sync', {'scope': scope, 'records': [first]})
    require_success(status, received, 'New QA OT and delivery')
    result, = received['results']
    assert result['client_uuid'] == first['client_uuid'] and result['ok'] is True and result['duplicate'] is False
    order_id, first_id = result['work_order_id'], result['id']
    assert positive_id(order_id) and positive_id(first_id)
    status, repeated_sync = client.request('POST', '/api/harvest/sync', {'scope': scope, 'records': [first]})
    require_success(status, repeated_sync, 'Original delivery retry')
    duplicate, = repeated_sync['results']
    assert duplicate['ok'] is True and duplicate['duplicate'] is True
    assert duplicate['client_uuid'] == first['client_uuid'] and duplicate['id'] == first_id and duplicate['work_order_id'] == order_id
    pending['work_order'] = {'odoo_id': order_id}
    payload = {'scope': scope, 'work_order': {'odoo_id': order_id}, 'delivery_uuids': [first['client_uuid']]}

    def current():
        status, data = client.request('GET', '/api/harvest/bootstrap')
        require_success(status, data, 'Native revised OT refresh')
        return next(row for row in data['orders'] if row.get('odoo_id') == order_id)

    def transition(action, expected, erp_state, **extra):
        status, value = client.request('POST', '/api/harvest/orders/transition', dict(payload, action=action, **extra))
        require_success(status, value, 'Copy ' + action)
        assert value.get('scope') == scope
        assert value['confirmed_delivery_uuids'] == extra.get('delivery_uuids', payload['delivery_uuids'])
        order = value['order']
        assert order['odoo_id'] == order_id and order['status'] == expected and order['erp_state'] == erp_state
        assert order['approver_id'] == policy['user_id']
        return value

    assert current()['approver_id'] == policy['user_id'] and current()['erp_state'] == 'in'
    status, rejected = client.request('POST', '/api/harvest/orders/transition', {
        'scope': altered, 'work_order': {'odoo_id': order_id}, 'action': 'close',
        'delivery_uuids': [first['client_uuid']]})
    assert status == 409 and rejected.get('ok') is False
    status, rejected = client.request('POST', '/api/harvest/orders/transition', {
        'scope': scope, 'work_order': {'odoo_id': order_id}, 'action': 'close',
        'delivery_uuids': [first['client_uuid'], run_uuid + '-MISSING']})
    assert status == 422 and rejected.get('ok') is False
    assert current()['status'] == 'En proceso'
    closed = transition('close', 'Cerrada', 'in')['order']
    assert transition('close', 'Cerrada', 'in')['order']['state_changed_at'] == closed['state_changed_at']
    assert closed['can_reopen'] is True
    status, rejected = client.request('POST', '/api/harvest/sync', {'scope': scope, 'records': [
        dict(pending, client_uuid=run_uuid + '-AFTER-CLOSE')]})
    assert status == 200 and rejected.get('ok') is False
    assert {row['mobile_uid'] for row in read_native_manifest(client, order_id)} == {first['client_uuid']}
    transition('reopen', 'En proceso', 'in')
    transition('close', 'Cerrada', 'in')
    approved = transition('approve', 'Revisada', 'apro')['order']
    assert approved['approved_by_id'] == policy['user_id'] and approved['approved_at']
    assert transition('approve', 'Revisada', 'apro')['order']['approved_at'] == approved['approved_at']
    full_manifest = [first['client_uuid'], pending['client_uuid']]
    status, rejected = client.request('POST', '/api/harvest/orders/transition', dict(payload, action='send',
        records=[pending], delivery_uuids=[*full_manifest, run_uuid + '-MISSING']))
    assert status == 422 and rejected.get('ok') is False
    assert {row['mobile_uid'] for row in read_native_manifest(client, order_id)} == {first['client_uuid']}, 'Incomplete total send must roll back its appended delivery'
    assert current()['erp_state'] == 'apro' and current()['status'] == 'Revisada'
    sent = transition('send', 'Enviada', 'apro', records=[pending], delivery_uuids=full_manifest)
    ack, = sent['results']
    assert ack['ok'] is True and ack['duplicate'] is False and ack['client_uuid'] == pending['client_uuid']
    assert ack['work_order_id'] == order_id and positive_id(ack['id']) and ack['id'] != first_id
    repeated = transition('send', 'Enviada', 'apro', records=[pending], delivery_uuids=full_manifest)
    retry, = repeated['results']
    assert retry['ok'] is True and retry['duplicate'] is True and retry['id'] == ack['id']
    assert repeated['order']['state_changed_at'] == sent['order']['state_changed_at']
    status, rejected = client.request('POST', '/api/harvest/orders/transition',
        dict(payload, action='reopen', delivery_uuids=full_manifest))
    assert status == 422 and rejected.get('ok') is False
    status, rejected = client.request('POST', '/api/harvest/sync', {'scope': scope, 'records': [
        dict(pending, client_uuid=run_uuid + '-AFTER-SENT')]})
    assert status == 200 and rejected.get('ok') is False
    manifest = read_native_manifest(client, order_id)
    assert {row['mobile_uid'] for row in manifest} == set(full_manifest) and len(manifest) == 2
    confirmed = current()
    assert confirmed['status'] == 'Enviada' and confirmed['erp_state'] == 'apro' and confirmed['can_reopen'] is False
    weight_evidence = {}
    if weights:
        assert confirmed['standard_weight'] and confirmed['packaging_id'] == packaging['id']
        assert confirmed['kg_per_box'] == packaging['kg_per_box']
        fields = ('qty_caja', 'qty_kg', 'quantity')
        expected = float((3 * Decimal(str(packaging['kg_per_box']))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
        for row in read_native_manifest(client, order_id, fields):
            assert (row['qty_caja'], row['qty_kg'], row['quantity']) == (3, expected, 3)
        manual_order = {key: work_order[key] for key in ('crew_id', 'farm_id', 'variety_id', 'cost_id', 'approver_id')}
        manual_order['id'] = manual_order['client_uuid'] = run_uuid + '-MANUAL-OT'
        manual = dict(first, client_uuid=run_uuid + '-MANUAL', work_order=manual_order, boxes=2, kilos=9.27)
        if version in ('0.0.11', '0.0.12'):
            assert bootstrap['allows_without_tarja'] is True
            manual_order['without_tarja'] = True
            manual['tarja'] = ''
        status, saved = client.request('POST', '/api/harvest/sync', {'scope': scope, 'records': [manual]})
        require_success(status, saved, 'Manual hundredths')
        result, = saved['results']
        assert result['ok'] is True and result['duplicate'] is False
        row, = read_native_manifest(client, result['work_order_id'], (*fields, 'num_tarja'))
        assert (row['qty_caja'], row['qty_kg'], row['quantity']) == (2, 9.27, 9.27)
        weight_evidence = {'native_standard_weight': True, 'native_manual_hundredths': True}
        if version in ('0.0.11', '0.0.12'):
            assert not row['num_tarja']
            status, closed = client.request('POST', '/api/harvest/orders/transition', {
                'scope': scope, 'work_order': {'odoo_id': result['work_order_id']}, 'action': 'close',
                'delivery_uuids': [manual['client_uuid']]})
            require_success(status, closed, 'Close without a tarja')
            assert closed['order']['without_tarja'] and closed['order']['status'] == 'Cerrada'
            weight_evidence['native_capture_without_tarja'] = True
    return {'run_uuid': run_uuid, 'native_order_id': order_id, 'native_line_id': first_id,
            'native_line_ids': [first_id, ack['id']], 'native_worker_id': worker_id, 'native_crew_id': crew['id'],
            'native_approver_id': policy['user_id'], 'new_lines': 2, 'native_context': True,
            'scope_rejected_before_write': True, 'native_copy_sync': True, 'sync_idempotency': True,
            'unconfirmed_delivery_blocks_close': True, 'ot_close': True, 'ot_review': True,
            'ot_send_confirmation': True, 'order_approver_selection': True, 'native_approval': True,
            'erp_state_approved': True, 'ot_reopen_before_send': True, 'sent_ot_cannot_reopen': True,
            'send_flushes_pending_deliveries': True, 'pending_send_atomic': True, 'send_retry_idempotency': True,
            'send_received_manifest': True,
            'close_retry_idempotency': True, 'new_delivery_rejected_after_close': True,
            'existing_relations_only': True, 'credentials_or_session_ids_supplied': False, **weight_evidence}


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
    exercise = exercise_revised_operations if policy['harvest_web']['version'] in REVISED_OPERATIONS_VERSIONS else exercise_operations
    evidence = exercise(OperationsClient(origin), policy)
    if policy['harvest_web']['version'] == '0.0.12':
        from smoke_harvest_work_hours import exercise_work_hours
        evidence.update(exercise_work_hours(origin, policy))
    evidence.update({'feature': proof['feature'], 'stage': stage.name, 'database': proof['database'],
        'web_commit': policy['harvest_web']['commit'], 'backend_commit': proof['commit'],
        'backend_sha256': proof['release_sha256'], 'created_at': datetime.now(timezone.utc).isoformat()})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    output.chmod(0o600)
    print('HARVEST_OPERATIONS_COPY_OK ' + json.dumps(evidence, sort_keys=True))


if __name__ == '__main__':
    main()
