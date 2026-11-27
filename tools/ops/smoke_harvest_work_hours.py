"""Exercise T244/T245 through the certified copy proxy only."""
from datetime import datetime, timedelta, timezone
import uuid

from smoke_harvest_operations import OperationsClient
from smoke_harvest_android_sync import require_success


def exercise_work_hours(origin, policy):
    assert policy['copy_sync_allowed'] is True and policy['read_only'] is False
    assert policy['harvest_web']['version'] == '0.0.12'
    client = OperationsClient(origin)
    status, data = client.request('GET', '/api/harvest/bootstrap')
    require_success(status, data, 'Hours bootstrap')
    workers = {row['id'] for row in data['workers']}
    crew, worker = next((crew, worker) for crew in data['crews']
                        for worker in crew.get('worker_ids', []) if worker in workers)
    center = next(row for row in data['cost_centers'] if row.get('farm_id') in {r['id'] for r in data['farms']}
                  and row.get('variety_id') in {r['id'] for r in data['varieties']})
    location = next((row for row in data['operation_locations'] if row['farm_id'] == center['farm_id']), None)
    token = 'QA-T244245-' + uuid.uuid4().hex
    base = datetime(2001, 2, 3, 8, tzinfo=timezone.utc)
    scope = data['scope']

    def create(suffix, passed=2, created=base):
        order = {'id': token + suffix, 'client_uuid': token + suffix, 'ot_fields_version': 1,
            'crew_id': crew['id'], 'farm_id': center['farm_id'], 'variety_id': center['variety_id'],
            'cost_id': center['id'], 'approver_id': policy['user_id'], 'pass_number': passed,
            'operation_location_id': location['id'] if location else False, 'harvest_type': 'export',
            'created_at': created.isoformat(), 'without_tarja': True}
        delivery = {'client_uuid': token + suffix + '-DELIVERY', 'worker_id': worker, 'work_order': order,
            'tarja': '', 'boxes': 1, 'kilos': 1, 'event_datetime': created.isoformat()}
        status, result = client.request('POST', '/api/harvest/sync', {'scope': scope, 'records': [delivery]})
        require_success(status, result, 'Hours OT creation') if passed else None
        return result, delivery

    rejected, _ = create('-INVALID', passed=0)
    assert rejected['ok'] is False and rejected['results'][0]['ok'] is False
    first_result, first_delivery = create('-FIRST')
    first_id = first_result['results'][0]['work_order_id']
    status, current = client.request('GET', '/api/harvest/bootstrap')
    require_success(status, current, 'Created OT')
    first = next(row for row in current['orders'] if row['odoo_id'] == first_id)
    assert (first['pass_number'], first['harvest_type'], first['operation_location_id']) == (
        2, 'export', location['id'] if location else False)
    path = f'/api/harvest/orders/hours?order_id={first_id}&day={first["order_day"]}'
    client.allowed_requests = (*client.allowed_requests, ('GET', path))
    status, summary = client.request('GET', path)
    require_success(status, summary, 'Crew day summary')
    assert summary['assigned_hours'] == 0 and not summary['day_closed']
    target = summary['day_hours']
    assert 0 < target <= 16, 'Review an unusual configured day before this fixture'
    half = target / 2
    middle, end = base + timedelta(hours=half), base + timedelta(hours=target)

    def close(order_id, delivery, start, end, hours, last=False):
        payload = {'scope': scope, 'work_order': {'odoo_id': order_id}, 'action': 'close',
            'delivery_uuids': [delivery['client_uuid']], 'work_time': {'start': start.isoformat(),
            'end': end.isoformat(), 'hours': hours, 'last_order': last}}
        return client.request('POST', '/api/harvest/orders/transition', payload)

    status, result = close(first_id, first_delivery, base, middle, half)
    require_success(status, result, 'First partial allocation')
    assert result['order']['work_hours'] == half and result['order']['status'] == 'Cerrada'
    second_result, second_delivery = create('-LAST', created=middle)
    second_id = second_result['results'][0]['work_order_id']
    status, invalid = close(second_id, second_delivery, middle, end, half / 2, True)
    assert status == 422 and invalid['ok'] is False
    status, final = close(second_id, second_delivery, middle, end, half, True)
    require_success(status, final, 'Final balanced allocation')
    assert final['order']['last_order'] and final['order']['day_hours'] == target
    status, retry = close(second_id, second_delivery, middle, end, half, True)
    require_success(status, retry, 'Final closure retry')
    assert retry['order'] == final['order']
    model = 'step.cosecha.registry.line' if crew['type'] == 'propio' else 'step.cosecha.tarja.line'
    native_path = '/web/dataset/call_kw/' + model + '/search_read'
    client.allowed_requests = (*client.allowed_requests, ('POST', native_path))
    status, native = client.request('POST', native_path, {'jsonrpc': '2.0', 'method': 'call', 'id': 1,
        'params': {'model': model, 'method': 'search_read', 'args': [[['registry_id', 'in', [first_id, second_id]]]],
            'kwargs': {'fields': ['id', 'registry_id', 'employee_id', 'hrs'], 'order': 'id'}}})
    assert status == 200 and not native.get('error') and native['result']
    lines = native['result']
    for order_id in (first_id, second_id):
        subset = [row for row in lines if row['registry_id'][0] == order_id]
        assert subset and all(row['hrs'] == half for row in subset)
        assert len({row['employee_id'][0] for row in subset}) == len(subset)
    return {'ot_native_fields': True, 'pass_required': True, 'ot_work_hours': True,
        'day_allocation': True, 'native_cost_hours': True, 'hours_order_ids': [first_id, second_id],
        'native_cost_line_ids': [row['id'] for row in lines], 'configured_day_hours': target}
