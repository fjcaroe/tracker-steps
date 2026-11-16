"""Rehearse and publish Steps Mobile updates on the isolated Development Tracker."""
import argparse
import fcntl
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from deploy_mobile_boarding import PY, assets, output, run, sha, tree
from deploy_mobile_progress import ENTRY, OVERLAYS, SERVICE, SNIPPET, TARGET, WEB, deployment_scope, dump, jornada_entry, postgres, verify

HEALTH_PATCH = 'routers/mobile.py'
HEALTH_DROPIN = Path('/etc/systemd/system/steps-tracker-dev-api.service.d/95-mobile-health.conf')


def certify(source, stage, effective, feature, case):
    archive = stage / 'development.dump'
    dump(TARGET, archive)
    copy = 'TRACKER_' + case + '_QA_' + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    scripts = stage / 'scripts'
    scripts.mkdir(mode=0o700)
    script = 'rehearse_mobile_' + feature + '.py'
    for name in (script, 'rehearse_passenger_services.py'):
        shutil.copy2(source / 'backend/tracker_py/scripts' / name, scripts)
    isolated_api = stage / 'api'
    shutil.copytree(effective / 'app', isolated_api / 'app', ignore=shutil.ignore_patterns('__pycache__', '.env*'))
    assert tree(isolated_api / 'app') == tree(effective / 'app')
    if feature == 'health':
        relative = 'backend/tracker_py/app/' + HEALTH_PATCH
        changed = output('git', '-C', source, 'log', '-1', '--format=%H', '--', relative)
        before = subprocess.check_output(['git', '-C', str(source), 'show', changed + '^:' + relative])
        assert (effective / 'app' / HEALTH_PATCH).read_bytes() == before, 'Concurrent mobile API change'
        shutil.copy2(source / relative, isolated_api / 'app' / HEALTH_PATCH)
    run('setfacl', '-m', 'u:postgres:--x', stage.parent, stage)
    run('setfacl', '-Rm', 'u:postgres:rX', scripts, isolated_api)
    postgres('createdb', copy)
    try:
        with archive.open('rb') as stream:
            postgres('pg_restore', '--no-owner', '--no-acl', '--no-comments', '-d', copy, stdin=stream)
        with (stage / 'postgres.log').open('wb') as log:
            run('sudo', '-u', 'postgres', 'env', 'DATABASE_URL=postgresql+psycopg2:///' + copy,
                'JWT_SECRET=disposable-mobile-copy-only', 'PYTHONPATH=' + str(isolated_api),
                PY, scripts / script, stdout=log, stderr=subprocess.STDOUT)
        assert f'TRACKER_{case}_POSTGRES_OK' in (stage / 'postgres.log').read_text()
    finally:
        postgres('dropdb', '--if-exists', copy)


def publish(front, entry, baseline, original, old_entry, stage, commit, feature, case, tested_api):
    backup = stage / 'nginx.conf.before'
    assert not backup.exists()
    shutil.copy2(SNIPPET, backup)
    target = WEB / commit
    entry_target = ENTRY / ('jornada-' + commit)
    assert not target.exists() and not entry_target.exists()
    shutil.copytree(front, target)
    old_assets, = set(re.findall(r'alias (/var/www/steps-mobile-releases/[a-f0-9]{40})/assets/;', original))
    for file in (Path(old_assets) / 'assets').iterdir():
        replacement = target / 'assets' / file.name
        if not replacement.exists():
            shutil.copy2(file, replacement)
    entry_target.mkdir()
    active_entry = entry_target / 'jornada.html'
    shutil.copy2(entry, active_entry)
    for root in (target, entry_target):
        root.chmod(0o755)
        for item in root.rglob('*'):
            item.chmod(0o755 if item.is_dir() else 0o644)
    revised, count = re.subn(r'/var/www/steps-mobile-releases/[a-f0-9]{40}/', str(target) + '/', original)
    assert count == 2 and revised.count(str(old_entry)) == 1
    revised = revised.replace(str(old_entry), str(active_entry))
    api_release = None
    if feature == 'health':
        api_release = OVERLAYS / commit
        assert not api_release.exists() and not HEALTH_DROPIN.exists()
        current = Path(baseline['working_directory'])
        assert current.is_relative_to(OVERLAYS)
        shutil.copytree(stage / 'api' / 'app', api_release / 'app', ignore=shutil.ignore_patterns('__pycache__'))
        assert tree(api_release / 'app') == tested_api
        (api_release / '.env').symlink_to((current / '.env').resolve(strict=True))
        for item in (api_release, *api_release.rglob('*')):
            if not item.is_symlink():
                item.chmod(0o755 if item.is_dir() else 0o644)

    try:
        if api_release:
            HEALTH_DROPIN.write_text('[Service]\nWorkingDirectory=' + str(api_release) + '\n')
            run('systemctl', 'daemon-reload')
            run('systemctl', 'restart', SERVICE)
            run('systemctl', 'is-active', '--quiet', SERVICE)
        SNIPPET.write_text(revised)
        run('nginx', '-t')
        run('nginx', '-s', 'reload')
        bundles = verify(front, active_entry, commit, baseline)
        scope = deployment_scope()
        changed_fields = {'nginx', 'entry', 'effective_api'}
        if api_release:
            changed_fields.update({'working_directory', 'service'})
            assert Path(scope['working_directory']) == api_release
        assert all(scope[key] == value for key, value in baseline.items() if key not in changed_fields)
        assert tree(Path(scope['working_directory']) / 'app') == tested_api
    except Exception:
        SNIPPET.write_text(original)
        run('nginx', '-t')
        run('nginx', '-s', 'reload')
        if api_release:
            HEALTH_DROPIN.unlink(missing_ok=True)
            run('systemctl', 'daemon-reload')
            run('systemctl', 'restart', SERVICE)
        raise
    (stage / 'delivery.json').write_text(json.dumps({'commit': commit, 'assets': bundles, 'backup': str(backup)}))
    print(f'TRACKER_{case}_DEVELOPMENT_OK', json.dumps(bundles), flush=True)


def main(feature='emergency'):
    case = {'emergency': 'I12', 'health': 'I15'}[feature]
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
    assert any(b'/tracker-dev-api' in item.read_bytes() for item in (front / 'assets').glob('*.js'))
    stage = Path('/opt/steps-validation/mobile-' + feature) / commit
    stage.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open('/run/lock/steps-environments.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        baseline = deployment_scope()
        effective = Path(baseline['working_directory'])
        baseline['effective_api'] = tree(effective / 'app')
        original = SNIPPET.read_text()
        old_entry, revised_entry = jornada_entry(front, original)
        baseline['entry'] = sha(old_entry)
        entry = stage / 'jornada.html'
        proof = {'baseline': baseline, 'assets': assets(front), 'entry': revised_entry}
        if args.action == 'qa':
            assert not (stage / 'qa.json').exists()
            entry.write_text(revised_entry)
            certify(source, stage, effective, feature, case)
            proof['api'] = tree(stage / 'api' / 'app')
            (stage / 'qa.json').write_text(json.dumps(proof))
            print(f'TRACKER_{case}_QA_OK', commit, flush=True)
        else:
            proof['api'] = tree(stage / 'api' / 'app')
            assert json.loads((stage / 'qa.json').read_text()) == proof
            assert entry.read_text() == revised_entry
            publish(front, entry, baseline, original, old_entry, stage, commit, feature, case, proof['api'])


if __name__ == '__main__':
    main()
