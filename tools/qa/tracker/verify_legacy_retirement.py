"""Read-only functional checks against the retired target copy, then seal its receipt."""
import json
import os
from pathlib import Path


def main():
    assert os.environ['DATABASE_URL'].rsplit('/', 1)[-1].startswith('TRACKER_CLEAN_QA_')
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.security import create_access_token
    from app.db.session import SessionLocal
    from app.models.users import User
    from app.models.fleet import Asset, Position, DeviceRegistration, Assignment, now
    from app.routers.fleet import asset_out
    proof_path = Path(os.environ['RETIREMENT_QA_RECEIPT'])
    proof = json.loads(proof_path.read_text())
    plan = json.loads(Path(os.environ['RETIREMENT_PLAN']).read_text())
    assert proof['qa'] and proof['database'] == os.environ['DATABASE_URL'].rsplit('/', 1)[-1]
    with SessionLocal() as db:
        admin = db.query(User).filter_by(is_admin=True, is_active=True).order_by(User.id).first()
        token = create_access_token({'sub': str(admin.id), 'username': admin.username})
        headers = {'Authorization': 'Bearer ' + token}
        with TestClient(app) as client:
            for path in ('/machines', '/sessions/my?status=open', '/sessions/my', '/work_orders', '/mobile/routes'):
                response = client.get(path, headers=headers)
                assert response.status_code == 200, (path, response.status_code)
                # This reviewed plan explicitly retires the complete legacy test collection.
                assert response.json() == [], path
        asset = db.get(Asset, plan['protected']['asset_id'])
        item = asset_out(db, asset, now())
        assert item['last_position'] and item['plate'] == plan['protect_plate']
        assert db.query(Position).filter_by(asset_id=asset.id).count() > 0
        assignment = db.query(Assignment).filter_by(asset_id=asset.id, valid_to=None).one()
        assert db.query(DeviceRegistration).filter_by(device_id=assignment.device_id).one().receiver_mode == 'forward'
    proof['functional_ok'] = True
    proof['functional_checks'] = ['empty_machine_selector', 'no_open_or_historic_test_journeys',
                                  'no_test_work_orders_or_routes', 'real_gps_asset_and_position_preserved']
    proof_path.write_text(json.dumps(proof, indent=2, sort_keys=True))
    print('LEGACY_RETIREMENT_COPY_FUNCTIONAL_OK')


if __name__ == '__main__':
    main()
