"""Rehearse and publish the I11 overlay for the isolated Development Tracker."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from dotenv import dotenv_values
from jose import jwt
from sqlalchemy.engine import make_url

from deploy_mobile_boarding import API, PY, assets, output, run, sha, tree


SERVICE = 'steps-tracker-dev-api.service'
TARGET = 'tracker_steps_development'
SNIPPET = Path('/etc/nginx/snippets/steps-tracker-dev-gps.conf')
BASE = Path('/opt/steps-validation/mobile-progress')
WEB = Path('/var/www/steps-mobile-releases')
OVERLAYS = Path('/opt/steps-tracker-development/releases')
DROPIN = Path('/etc/systemd/system/steps-tracker-dev-api.service.d/90-service-progress.conf')
PUBLIC = 'https://desarrollo.stepsapp.cl'
PATCH = ('models/__init__.py', 'models/passenger_services.py', 'routers/passenger_services.py')


def postgres(command, *args, **kwargs):
    return run('sudo', '-u', 'postgres', command, *args, **kwargs)


def dump(database, path):
    with path.open('wb') as stream:
        postgres('pg_dump', '-Fc', database, stdout=stream)
    run('pg_restore', '--file=/dev/null', path)


def migrate(database, migration):
    for _ in range(2):
        with migration.open('rb') as stream:
            postgres('psql', '-Xq', '-v', 'ON_ERROR_STOP=1', '-d', database, stdin=stream)
    grants = """DO $$ DECLARE item record; BEGIN
      FOR item IN SELECT grantee, privilege_type FROM information_schema.role_table_grants
        WHERE table_schema='public' AND table_name='mobile_passenger_events'
      LOOP EXECUTE format('GRANT %s ON TABLE mobile_service_progress_events TO %I',
                          item.privilege_type, item.grantee);
      END LOOP;
    END $$;"""
    postgres('psql', '-Xq', '-v', 'ON_ERROR_STOP=1', '-d', database, '-c', grants)


def deployment_scope():
    cfg = Path('/etc/steps-tracker-development.env')
    assert make_url(dotenv_values(cfg)['DATABASE_URL']).database == TARGET
    return {
        'working_directory': output('systemctl', 'show', '--value', '-p', 'WorkingDirectory', SERVICE),
        'service': hashlib.sha256(output('systemctl', 'cat', SERVICE).encode()).hexdigest(),
        'nginx': sha(SNIPPET),
        'production_api': tree(API / 'app'),
        'production_truck': sha(Path('/var/www/steps-truck-frontend/index.html')),
        'production_web': sha(Path('/var/www/web_tracker/index.html')),
        'cerro': sha(Path('/etc/nginx/snippets/steps-tracker-cerro-gps.conf')),
        'gps_receiver': tree(Path('/opt/steps-coban/current').resolve() / 'receivers'),
    }


def verify(front, commit, baseline):
    settings = dotenv_values(API / '.env')
    driver = output('sudo', '-u', 'postgres', 'psql', '-XAt', '-d', TARGET, '-c',
                    'SELECT driver_user_id FROM mobile_passenger_services ORDER BY created_at DESC LIMIT 1')
    assert driver and driver.isdecimal(), 'An existing Development service is required'
    session = jwt.encode({'sub': driver, 'exp': int(time.time()) + 300}, settings['JWT_SECRET'], algorithm='HS256')
    paths = '/mobile/services/{service_id}/progress'
    for _ in range(35):
        try:
            with urlopen(PUBLIC + '/tracker-dev-api/openapi.json', timeout=6) as response:
                assert paths in json.load(response)['paths']
            with urlopen(PUBLIC + '/truck/', timeout=6) as response:
                if hashlib.sha256(response.read()).hexdigest() == sha(front / 'index.html'):
                    break
        except (OSError, AssertionError):
            pass
        time.sleep(1)
    else:
        raise RuntimeError('The tested API and UI are not served by Development')
    headers = {'Authorization': 'Bearer ' + session}
    with urlopen(Request(PUBLIC + '/tracker-dev-api/mobile/services?mine=true', headers=headers), timeout=15) as response:
        services = json.load(response)
    assert services
    service = services[0]
    with urlopen(Request(PUBLIC + '/tracker-dev-api/mobile/services/' + service['id'] + '/progress',
                         headers=headers), timeout=15) as response:
        progress = json.load(response)
        assert progress['stops'] and progress['id'] == service['id']
    for file, expected in assets(front).items():
        with urlopen(PUBLIC + '/truck/' + file, timeout=25) as response:
            assert hashlib.sha256(response.read()).hexdigest() == expected, file
    scope = deployment_scope()
    assert all(scope[k] == baseline[k] for k in ('production_api', 'production_truck', 'production_web', 'cerro', 'gps_receiver'))
    bundles = {name: digest for name, digest in assets(front).items()
               if name.startswith('assets/index-') and name.endswith('.js')}
    print('TRACKER_I11_DEVELOPMENT_OK ' + json.dumps({'commit': commit, 'assets': bundles,
          'existing_service_read': True}), flush=True)
    return bundles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('qa', 'deploy'))
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    assert os.geteuid() == 0
    os.umask(0o077)
    source = args.source.resolve()
    commit = output('git', '-C', source, 'rev-parse', 'HEAD')
    assert not output('git', '-C', source, 'status', '--porcelain', '--untracked-files=no')
    front = source / 'mobile/dist'
    assert any(b'/tracker-dev-api' in p.read_bytes() for p in (front / 'assets').glob('*.js'))
    stage = BASE / commit
    stage.mkdir(parents=True, exist_ok=True, mode=0o700)
    api_source = source / 'backend/tracker_py'
    migration = api_source / 'migrations/20261115_service_progress.up.sql'
    overlay = stage / 'overlay'
    with open('/run/lock/steps-environments.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        baseline = deployment_scope()
        effective = Path(baseline['working_directory'])
        assert effective.is_relative_to('/opt/steps-tracker-analytics/releases/development') or effective.is_relative_to(OVERLAYS)
        baseline['effective_api'] = tree(effective / 'app')
        if args.action == 'qa':
            assert not overlay.exists()
            for path in PATCH:
                previous = subprocess.check_output(['git', '-C', str(source), 'show',
                                                    'HEAD^:backend/tracker_py/app/' + path])
                assert (effective / 'app' / path).read_bytes() == previous, path
            (overlay / 'app').mkdir(parents=True, mode=0o755)
            shutil.copytree(effective / 'app', overlay / 'app', dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns('__pycache__'))
            for path in PATCH:
                shutil.copy2(api_source / 'app' / path, overlay / 'app' / path)
            path_hashes = tree(overlay / 'app')
            assert {p: v for p, v in path_hashes.items() if p not in PATCH} == {
                p: v for p, v in baseline['effective_api'].items() if p not in PATCH}
            archive = stage / 'development.dump'
            dump(TARGET, archive)
            copy = 'TRACKER_I11_QA_' + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
            postgres('createdb', copy)
            try:
                with archive.open('rb') as stream:
                    postgres('pg_restore', '--no-owner', '--no-acl', '--no-comments', '-d', copy, stdin=stream)
                migrate(copy, migration)
                scripts = stage / 'qa-scripts'
                scripts.mkdir(mode=0o700)
                for filename in ('rehearse_service_progress.py', 'rehearse_passenger_services.py'):
                    shutil.copy2(api_source / 'scripts' / filename, scripts)
                run('setfacl', '-m', 'u:postgres:--x', BASE, stage, overlay)
                run('setfacl', '-Rm', 'u:postgres:rX', overlay / 'app', scripts)
                with (stage / 'functional.log').open('wb') as log:
                    run('sudo', '-u', 'postgres', 'env', 'DATABASE_URL=postgresql+psycopg2:///' + copy,
                        'JWT_SECRET=disposable-i11-clone-only', 'PYTHONPATH=' + str(overlay),
                        PY, scripts / 'rehearse_service_progress.py', stdout=log, stderr=subprocess.STDOUT)
                assert 'TRACKER_I11_POSTGRES_OK' in (stage / 'functional.log').read_text()
            finally:
                postgres('dropdb', '--if-exists', copy)
            (stage / 'qa.json').write_text(json.dumps({'baseline': baseline, 'api': path_hashes,
                'assets': assets(front), 'migration': sha(migration)}, indent=2))
            print('TRACKER_I11_QA_OK', flush=True)
            return

        proof = json.loads((stage / 'qa.json').read_text())
        assert proof == {'baseline': baseline, 'api': tree(overlay / 'app'),
                         'assets': assets(front), 'migration': sha(migration)}
        assert not DROPIN.exists() and not (OVERLAYS / commit).exists() and not (WEB / commit).exists()
        backup = stage / ('backup-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        backup.mkdir(mode=0o700)
        shutil.copy2(SNIPPET, backup / 'nginx.conf')
        dump(TARGET, backup / 'development.dump')
        api_release = OVERLAYS / commit
        web_release = WEB / commit
        shutil.copytree(overlay, api_release)
        (api_release / '.env').symlink_to((effective / '.env').resolve(strict=True))
        shutil.copytree(front, web_release)
        for root in (api_release, web_release):
            root.chmod(0o755)
            for item in root.rglob('*'):
                if not item.is_symlink():
                    item.chmod(0o755 if item.is_dir() else 0o644)
        old = SNIPPET.read_text()
        new, count = re.subn(r'/var/www/steps-mobile-releases/[a-f0-9]{40}/',
                             str(web_release) + '/', old)
        assert count == 2 and new != old
        migrate(TARGET, migration)
        try:
            DROPIN.write_text('[Service]\nWorkingDirectory=' + str(api_release) + '\n')
            run('systemctl', 'daemon-reload')
            run('systemctl', 'restart', SERVICE)
            run('systemctl', 'is-active', '--quiet', SERVICE)
            SNIPPET.write_text(new)
            run('nginx', '-t')
            run('systemctl', 'reload', 'nginx')
            bundles = verify(front, commit, baseline)
        except Exception:
            SNIPPET.write_text(old)
            run('nginx', '-t')
            run('systemctl', 'reload', 'nginx')
            DROPIN.unlink(missing_ok=True)
            run('systemctl', 'daemon-reload')
            run('systemctl', 'restart', SERVICE)
            raise
        (stage / 'delivery.json').write_text(json.dumps({'commit': commit, 'backup': str(backup),
            'target': TARGET, 'assets': bundles, 'postgres_rehearsal': True, 'served': True}, indent=2))


if __name__ == '__main__':
    main()
