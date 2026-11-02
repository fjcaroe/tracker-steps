"""I10: real HTTP/ORM, ordered offline receipts and live authorization."""
from copy import deepcopy
from datetime import datetime, timezone
import uuid
import pytest
from tests.test_passenger_services import api  # noqa: F401
from app.models.mobile import MobileRoute
from app.models.users import UserCostCenter
from app.models.passenger_services import PassengerEvent


def ready(api):
    client, who, factory, body = api
    assert client.post('/mobile/services', json=body).status_code == 200
    who['id'] = 2
    return client, who, factory, body, '/mobile/services/' + body['id']


def event(body, passenger=0, kind='boarded', version=0):
    return dict(id=str(uuid.uuid4()), passenger_id=body['passengers'][passenger]['id'], kind=kind,
                expected_version=version, occurred_at=datetime.now(timezone.utc).isoformat(),
                lat=None, lon=None, accuracy_m=None)


def test_complete_offline_manifest_retries_once_and_keeps_captured_time(api):
    client, _, factory, body, path = ready(api)
    queued = [event(body, 0, 'boarded', 0), event(body, 1, 'boarded', 1),
              event(body, 2, 'no_show', 2), event(body, 0, 'alighted', 3), event(body, 1, 'alighted', 4)]
    for value in queued:
        value.update(lat=-33.4, lon=-70.5, accuracy_m=12)
        for _ in range(2):
            response = client.post(path + '/events', json=value)
            assert response.status_code == 200, response.text
    result = client.get(path + '/manifest')
    assert result.headers['cache-control'] == 'no-store'
    result = result.json()
    assert result['occupied'] == 0 and result['manifest_version'] == 5
    assert [e['id'] for e in result['events']] == [e['id'] for e in queued]
    assert {p['state'] for p in result['passengers']} == {'alighted', 'no_show'}
    assert result['sync']['schema_version'] == 2
    with factory() as db:
        assert db.query(PassengerEvent).count() == 5
        assert all(e.actor_id == 2 and e.accuracy_m == 12 for e in db.query(PassengerEvent))


def test_stale_phone_and_uuid_payload_collision_never_overwrite(api):
    client, _, _, body, path = ready(api)
    first = event(body)
    assert client.post(path+'/events', json=first).status_code == 200
    assert client.post(path+'/events', json=event(body, 1)).status_code == 409
    changed = deepcopy(first); changed['kind'] = 'alighted'
    assert client.post(path+'/events', json=changed).status_code == 409
    assert client.post(path+'/events', json=first).json()['manifest_version'] == 1


@pytest.mark.parametrize('kind', ['wrong_passenger', 'alight_before_board', 'invalid_location', 'future_time', 'old_time'])
def test_invalid_events_are_atomic(api, kind):
    client, _, factory, body, path = ready(api)
    value = event(body)
    if kind == 'wrong_passenger': value['passenger_id'] = str(uuid.uuid4())
    if kind == 'alight_before_board': value['kind'] = 'alighted'
    if kind == 'invalid_location': value['lat'] = 0
    if kind == 'future_time': value['occurred_at'] = '2099-01-01T00:00:00Z'
    if kind == 'old_time': value['occurred_at'] = '2000-01-01T00:00:00Z'
    assert client.post(path+'/events', json=value).status_code in (409, 422)
    with factory() as db: assert db.query(PassengerEvent).count() == 0


def test_live_driver_cost_center_and_cancellation_checks(api):
    client, who, factory, body, path = ready(api)
    value = event(body)
    who['id'] = 3
    assert client.post(path+'/events', json=value).status_code == 404
    assert client.get(path+'/manifest').status_code == 404
    who['id'] = 2
    with factory() as db:
        db.get(MobileRoute, uuid.UUID(body['route_id'])).status = 'cancelled'; db.commit()
    assert client.post(path+'/events', json=value).status_code == 409
    with factory() as db:
        db.query(UserCostCenter).filter_by(user_id=2).delete(); db.commit()
    assert client.get(path+'/manifest').status_code == 403
    assert client.post(path+'/events', json=value).status_code == 403


def test_seat_reuse_requires_real_descent_and_capacity_is_live(api):
    client, who, factory, body = api
    body['passengers'][0]['alighting_stop_id'] = body['stops'][1]['id']
    body['passengers'][1]['boarding_stop_id'] = body['stops'][1]['id']
    body['passengers'][1]['seat'] = 1
    assert client.post('/mobile/services', json=body).status_code == 200
    who['id'] = 2; path = '/mobile/services/' + body['id']
    assert client.post(path+'/events', json=event(body)).status_code == 200
    assert client.post(path+'/events', json=event(body, 1, version=1)).status_code == 409
    assert client.post(path+'/events', json=event(body, 0, 'alighted', 1)).status_code == 200
    assert client.post(path+'/events', json=event(body, 1, version=2)).status_code == 200
    # Historical capacity remains authoritative even if current vehicle capacity changes.
    assert client.post(path+'/events', json=event(body, 2, version=3)).json()['occupied'] == 2


def test_no_show_can_be_corrected_by_actual_boarding_but_completed_passenger_cannot_reboard(api):
    client, _, _, body, path = ready(api)
    for version, kind in enumerate(['no_show', 'boarded', 'alighted']):
        assert client.post(path+'/events', json=event(body, kind=kind, version=version)).status_code == 200
    assert client.post(path+'/events', json=event(body, version=3)).status_code == 409


def test_real_boarding_cannot_exceed_historic_capacity_even_when_planned_legs_allow_it(api):
    client, who, factory, body = api
    body['passengers'][0]['alighting_stop_id'] = body['stops'][1]['id']
    extra = deepcopy(body['passengers'][0]); extra.update(id=str(uuid.uuid4()), name='Fourth', document='FOURTH', seat=None,
        boarding_stop_id=body['stops'][1]['id'], alighting_stop_id=body['stops'][2]['id'])
    body['passengers'].append(extra)
    assert client.post('/mobile/services', json=body).status_code == 200
    who['id'] = 2; path = '/mobile/services/' + body['id']
    for i in range(3): assert client.post(path+'/events', json=event(body, i, version=i)).status_code == 200
    result = client.post(path+'/events', json=event(body, 3, version=3))
    assert result.status_code == 409 and 'Capacidad completa' in result.json()['detail']
    assert client.get(path+'/manifest').json()['occupied'] == 3
