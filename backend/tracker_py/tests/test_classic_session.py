from app.db.base import Base
from app.models.cost_centers import CostCenter
from app.models.users import User, UserCostCenter
from tests.test_fleet import fleet, headers  # noqa: F401


def prepare(factory):
    Base.metadata.create_all(factory.kw['bind'], tables=[User.__table__, UserCostCenter.__table__, CostCenter.__table__])


def test_odoo_identity_gets_classic_token_without_password(fleet):  # noqa: F811
    client, factory = fleet
    prepare(factory)
    body = {'login': 'ana@steps.cl', 'name': 'Ana Pérez'}
    assert client.post('/v1/classic-session', json=body).status_code == 401
    assert client.post('/v1/classic-session', json=body, headers=headers(role='viewer')).status_code == 403
    first = client.post('/v1/classic-session', json=body, headers=headers(role='manager', user='7'))
    assert first.status_code == 200
    data = first.json()
    assert data['user']['is_admin'] is True and data['user']['full_name'] == 'Ana Pérez'
    assert client.get('/auth/me', headers={'Authorization': 'Bearer ' + data['access_token']}).status_code == 200
    again = client.post('/v1/classic-session', json=body, headers=headers(role='operator', user='7')).json()
    assert again['user']['id'] == data['user']['id'] and again['user']['is_admin'] is False
    other = client.post('/v1/classic-session', json=body, headers=headers(issuer='test-two', role='manager', user='7')).json()
    assert other['user']['id'] != data['user']['id']
    with factory() as db:
        assert db.query(User).count() == 2
