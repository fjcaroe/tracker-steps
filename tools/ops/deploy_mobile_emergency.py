"""Rehearse and publish the I12 frontend on the isolated Development Tracker."""
import argparse
import fcntl
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from deploy_mobile_boarding import PY, assets, output, run, sha, tree
from deploy_mobile_progress import ENTRY, SNIPPET, TARGET, WEB, deployment_scope, dump, jornada_entry, postgres, verify

BASE = Path('/opt/steps-validation/mobile-emergency')


def certify(source, stage, effective):
    archive = stage / 'development.dump'
    dump(TARGET, archive)
    copy = 'TRACKER_I12_QA_' + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    scripts = stage / 'scripts'
    scripts.mkdir(mode=0o700)
    for name in ('rehearse_mobile_emergency.py', 'rehearse_passenger_services.py'):
        shutil.copy2(source / 'backend/tracker_py/scripts' / name, scripts)
    run('setfacl', '-m', 'u:postgres:--x', BASE, stage)
    run('setfacl', '-Rm', 'u:postgres:rX', scripts)
    postgres('createdb', copy)
    try:
        with archive.open('rb') as stream:
            postgres('pg_restore', '--no-owner', '--no-acl', '--no-comments', '-d', copy, stdin=stream)
        with (stage / 'postgres.log').open('wb') as log:
            run('sudo', '-u', 'postgres', 'env', 'DATABASE_URL=postgresql+psycopg2:///' + copy,
                'JWT_SECRET=disposable-i12-copy-only', 'PYTHONPATH=' + str(effective),
                PY, scripts / 'rehearse_mobile_emergency.py', stdout=log, stderr=subprocess.STDOUT)
        assert 'TRACKER_I12_POSTGRES_OK' in (stage / 'postgres.log').read_text()
    finally:
        postgres('dropdb', '--if-exists', copy)


def publish(front, entry, baseline, original, old_entry, stage, commit):
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
    try:
        SNIPPET.write_text(revised)
        run('nginx', '-t')
        run('nginx', '-s', 'reload')
        bundles = verify(front, active_entry, commit, baseline)
        scope = deployment_scope()
        assert all(scope[key] == value for key, value in baseline.items() if key not in ('nginx', 'entry', 'effective_api'))
        assert tree(Path(scope['working_directory']) / 'app') == baseline['effective_api']
    except Exception:
        SNIPPET.write_text(original)
        run('nginx', '-t')
        run('nginx', '-s', 'reload')
        raise
    (stage / 'delivery.json').write_text(json.dumps({'commit': commit, 'assets': bundles, 'backup': str(backup)}))
    print('TRACKER_I12_DEVELOPMENT_OK', json.dumps(bundles), flush=True)


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
    assert any(b'/tracker-dev-api' in item.read_bytes() for item in (front / 'assets').glob('*.js'))
    stage = BASE / commit
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
            certify(source, stage, effective)
            (stage / 'qa.json').write_text(json.dumps(proof))
            print('TRACKER_I12_QA_OK', commit, flush=True)
        else:
            assert json.loads((stage / 'qa.json').read_text()) == proof
            assert entry.read_text() == revised_entry
            publish(front, entry, baseline, original, old_entry, stage, commit)


if __name__ == '__main__':
    main()
