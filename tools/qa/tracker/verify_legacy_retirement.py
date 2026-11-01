"""Read-only functional checks against the retired target copy, then seal its receipt."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import Request, urlopen


def main():
    assert os.environ['DATABASE_URL'].rsplit('/', 1)[-1].startswith('TRACKER_CLEAN_QA_')
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
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        log_path = proof_path.with_suffix('.http.log')
        with log_path.open('w') as log:
            os.chmod(log_path, 0o600)
            server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app',
                                       '--host', '127.0.0.1', '--port', str(port),
                                       '--no-access-log', '--lifespan', 'off'], stdout=log, stderr=log)
            try:
                for _ in range(75):
                    assert server.poll() is None, 'Private copy API stopped; inspect its private log'
                    try:
                        with socket.create_connection(('127.0.0.1', port), timeout=.2):
                            break
                    except OSError:
                        time.sleep(.2)
                else:
                    raise RuntimeError('Private copy API did not become ready')
                for path in ('/machines', '/sessions/my?status=open', '/sessions/my', '/work_orders', '/mobile/routes'):
                    with urlopen(Request('http://127.0.0.1:'+str(port)+path, headers=headers), timeout=15) as response:
                        assert response.status == 200, path
                        # This reviewed plan retires the complete legacy test collection.
                        assert json.load(response) == [], path
            finally:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)
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
