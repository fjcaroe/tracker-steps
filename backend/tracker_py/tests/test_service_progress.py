"""Exercise arrival, delay, supervisor visibility, and immutable manifest signing."""
from tests.test_passenger_services import api  # noqa: F401
from tests.test_passenger_events import event, ready
import uuid


def test_progress_records_route_and_closes_the_current_manifest(api):
    client, who, _, body, path = ready(api)
    first = body['stops'][0]['id']
    progress = path + '/progress'
    data = dict(id=str(uuid.uuid4()), kind='arrived', stop_id=first, expected_version=0, notes='Desvío informado')
    assert client.get('/mobile/services/progress').status_code == 403
    assert client.post(progress, json={**data, 'stop_id': body['stops'][1]['id']}).status_code == 409
    saved = client.post(progress, json=data)
    assert saved.status_code == 200, saved.text
    assert saved.headers['cache-control'] == 'no-store'
    assert saved.json()['stops'][1]['eta']
    assert saved.json()['stops'][1]['delay_minutes'] > 0
    assert client.post(progress, json=data).json()['version'] == 1
    assert client.post(progress, json={**data, 'notes': 'Different'}).status_code == 409
    who['id'] = 3
    assert client.get(progress).status_code == 404
    who['id'] = 1
    progress_list = client.get('/mobile/services/progress').json()
    assert progress_list[0]['stops'][0]['arrival_notes'] == 'Desvío informado'
    assert 'passengers' not in progress_list[0]
    assert client.post(progress, json=data).status_code == 403
    who['id'] = 2

    version = 0
    for stop in body['stops']:
        for kind in ('arrived', 'departed'):
            update = data if version == 0 else dict(
                id=str(uuid.uuid4()), kind=kind, stop_id=stop['id'], expected_version=version,
            )
            assert client.post(progress, json=update).status_code == 200
            version += 1
    close = dict(id=str(uuid.uuid4()), kind='closed', expected_version=version, manifest_version=0,
                 signature='Private driver signature', notes='Última novedad')
    assert client.post(progress, json=close).status_code == 409
    for passenger in range(3):
        assert client.post(path + '/events', json=event(body, passenger, 'no_show', passenger)).status_code == 200
    manifest = client.get(path + '/manifest').json()
    assert client.post(progress, json=close).status_code == 409
    close['manifest_version'] = manifest['manifest_version']
    result = client.post(progress, json=close)
    assert result.status_code == 200, result.text
    record = result.json()['closure']
    assert record['manifest_hash'] == manifest['sync']['content_hash']
    assert record['signature'] == close['signature'] and record['actor_id'] == 2
    assert client.post(progress, json=close).json()['closure'] == record
    assert client.get(path + '/manifest').json()['service_closed']
    assert client.post(path + '/events', json=event(body, 0, 'boarded', 3)).status_code == 409
