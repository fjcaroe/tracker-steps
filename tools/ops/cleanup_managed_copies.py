"""One-time cleanup of old managed Odoo backups and completed validation copies."""
import argparse
import configparser
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess


BACKUPS = Path('/opt/steps_backups')
VALIDATION = Path('/opt/steps-validation')
RELEASES = Path('/opt/steps-managed/releases')
LOCK = '/run/lock/steps-environments.lock'
TARGETS = ('development', 'cerro', 'qa-cerro', 'sys', 'demo-sys', 'steps')
BACKUP_NAME = re.compile(r'management_([a-z-]+)_(\d{8}T\d{6}Z)')
RUN_NAME = re.compile(r'management_([a-z-]+)_([a-z0-9_]{1,24})')
COMMIT = re.compile(r'[0-9a-f]{40}')
ATTACHMENT = re.compile(r'[0-9a-f]{2}/[0-9a-f]{40}')
POSTGRES = ('sudo', '-u', 'postgres')


def psql(database):
    return (*POSTGRES, 'psql', '-XqAt', '-v', 'ON_ERROR_STOP=1', '-d', database)


def read_sql(database, statement):
    return subprocess.check_output([*psql(database), '-c', statement], text=True).splitlines()


def config(path):
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(path)
    return parser['options']


def manifest(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def runtime_references():
    references = []
    for process in Path('/proc').glob('[0-9]*'):
        if process.name == str(os.getpid()):
            continue
        try:
            if (process / 'comm').read_text().strip() in ('du', 'find'):
                continue
            references.append((process / 'cmdline').read_text(errors='replace'))
            for node in [process / 'cwd', *(process / 'fd').iterdir()]:
                try:
                    references.append(os.readlink(node))
                except OSError:
                    pass
        except OSError:
            continue
    etc = Path('/etc')
    for pattern in ('*odoo*.conf', 'systemd/system/**/*.service', 'systemd/system/**/*.service.d/*.conf'):
        for path in etc.glob(pattern):
            if path.is_file():
                references.append(path.read_text(errors='replace'))
    return references


def referenced(references, *tokens):
    return any(token in value for value in references for token in tokens)


def local_path(path, root):
    return (path.is_relative_to(root) and path != root and path.resolve() == path
            and path.stat().st_dev == root.stat().st_dev)


def backup_groups(targets):
    groups = {name: [] for name in targets}
    for path in sorted(BACKUPS.iterdir()):
        match = BACKUP_NAME.fullmatch(path.name)
        if not match or match[1] not in groups or not path.is_dir() or not local_path(path, BACKUPS):
            continue
        try:
            if config(path / 'odoo.conf').get('db_name') != targets[match[1]]['database']:
                continue
        except KeyError:
            continue
        groups[match[1]].append(path)
    return groups


def inventory(targets, cutoff):
    groups = backup_groups(targets)
    references = runtime_references()
    existing = set(read_sql('postgres', 'SELECT datname FROM pg_database'))
    active = set(read_sql('postgres', 'SELECT DISTINCT datname FROM pg_stat_activity WHERE datname IS NOT NULL'))
    published = {name: {manifest(path / 'deployment.json').get('commit') for path in backups}
                 for name, backups in groups.items()}
    backups = {}
    copies = []
    for name, paths in groups.items():
        old = [str(path) for path in paths[:-1] if path.stat().st_mtime < cutoff
               and not referenced(references, str(path))]
        if old:
            backups[name] = old
    protected = {target['database'] for target in targets.values()}
    for stage in sorted(VALIDATION.iterdir()):
        match = RUN_NAME.fullmatch(stage.name)
        if not match or match[1] not in groups or not stage.is_dir() or not local_path(stage, VALIDATION):
            continue
        target, run_id = match.groups()
        proof_path = stage / 'qa_passed.json'
        proof = manifest(proof_path)
        database = 'MANAGEMENT_QA_' + target.upper() + '_' + run_id
        commit = proof.get('commit', '')
        if (proof.get('database') != database or not COMMIT.fullmatch(commit)
                or commit not in published[target]
                or proof_path.stat().st_mtime >= cutoff or stage.stat().st_mtime >= cutoff
                or database in protected or database in active or referenced(references, str(stage), database)):
            continue
        release = manifest(RELEASES / target / commit / 'release.json')
        if release.get('commit') != commit:
            continue
        payloads = [stage / 'source.dump', stage / 'data' / 'filestore' / database]
        paths = [str(path) for path in payloads if path.exists() and local_path(path, VALIDATION)]
        if paths or database in existing:
            copies.append({'target': target, 'database': database, 'exists': database in existing, 'paths': paths})
    return {'old_backups': backups, 'completed_copies': copies}


def fresh_backup(target, entry):
    source_config = Path(entry['config'])
    options = config(source_config)
    database = entry['database']
    assert options.get('db_name') == database
    store = Path(options['data_dir']) / 'filestore' / database
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    destination = BACKUPS / f'retained_{target}_{stamp}'
    destination.mkdir(mode=0o700)
    shutil.copyfile(source_config, destination / 'odoo.conf')
    snapshot = subprocess.Popen(psql(database), stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        snapshot.stdin.write('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SELECT pg_export_snapshot();\n')
        snapshot.stdin.flush()
        snapshot_id = snapshot.stdout.readline().strip()
        assert re.fullmatch(r'[0-9A-Fa-f-]+', snapshot_id)
        files = subprocess.check_output(psql(database), input=(
            "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SET TRANSACTION SNAPSHOT '" + snapshot_id + "';"
            "SELECT DISTINCT store_fname FROM ir_attachment WHERE COALESCE(store_fname,'')<>''; COMMIT;"
        ), text=True).splitlines()
        assert all(ATTACHMENT.fullmatch(name) for name in files)
        dump = destination / 'database.dump'
        with dump.open('wb') as stream:
            subprocess.run([*POSTGRES, 'pg_dump', '-Fc', '--snapshot=' + snapshot_id, database],
                           stdout=stream, check=True)
        filestore = destination / 'filestore'
        filestore.mkdir(mode=0o700)
        if store.is_dir():
            subprocess.run(['rsync', '-a', str(store) + '/', str(filestore) + '/'], check=True)
        missing = sum(not (filestore / name).is_file() for name in files)
        subprocess.run(['pg_restore', '-f', '/dev/null', str(dump)], check=True)
        record = {'database': database, 'files_referenced': len(files), 'missing_files': missing}
        (destination / 'retention.json').write_text(json.dumps(record))
        print('RETAINED', target, destination.name, json.dumps(record), flush=True)
        return not missing
    finally:
        snapshot.stdin.close()
        snapshot.wait()


def remove_path(path, root):
    assert local_path(path, root) and not path.is_symlink()
    mounts = [Path(line.split()[4]) for line in Path('/proc/self/mountinfo').read_text().splitlines()]
    assert not any(mount.is_relative_to(path) for mount in mounts), str(path)
    if path.is_dir():
        shutil.rmtree(path)
    else:
        assert path.is_file()
        path.unlink()


def free_bytes():
    info = os.statvfs('/')
    return info.f_bavail * info.f_frsize


def apply(plan, targets, cutoff):
    assert inventory(targets, cutoff) == plan, 'The candidate inventory changed; regenerate the plan'
    before = free_bytes()
    affected = set(plan['old_backups']) | {copy['target'] for copy in plan['completed_copies']}
    retained = set()
    for target in sorted(affected):
        try:
            if fresh_backup(target, targets[target]):
                retained.add(target)
        except (AssertionError, OSError, subprocess.CalledProcessError) as error:
            print('BACKUP_NOT_VERIFIED', target, type(error).__name__, flush=True)
    removed = {'backups': 0, 'databases': 0, 'payloads': 0}
    references = runtime_references()
    for copy in plan['completed_copies']:
        if copy['target'] not in retained:
            continue
        database = copy['database']
        if referenced(references, database, *copy['paths']):
            print('SKIP_IN_USE', database, flush=True)
            continue
        if copy['exists']:
            result = subprocess.run([*POSTGRES, 'dropdb', '--', database])
            if result.returncode:
                print('SKIP_DATABASE', database, flush=True)
                continue
            removed['databases'] += 1
        for name in copy['paths']:
            remove_path(Path(name), VALIDATION)
            removed['payloads'] += 1
        if removed['databases'] and removed['databases'] % 25 == 0:
            print('CLEANUP_PROGRESS', json.dumps(removed), flush=True)
    for target, paths in plan['old_backups'].items():
        if target not in retained:
            continue
        for name in paths:
            if referenced(references, name):
                print('SKIP_IN_USE', Path(name).name, flush=True)
                continue
            remove_path(Path(name), BACKUPS)
            removed['backups'] += 1
    result = {'removed': removed, 'bytes_reclaimed': free_bytes() - before,
              'free_bytes': free_bytes(), 'skipped_targets': sorted(affected - retained)}
    print('CLEANUP_DONE', json.dumps(result), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('plan', 'apply'))
    parser.add_argument('plan', type=Path)
    parser.add_argument('--registry', type=Path, required=True)
    args = parser.parse_args()
    assert os.geteuid() == 0 and socket.gethostname().split('.')[0] == 'odoo-new'
    os.umask(0o077)
    configured = json.loads(args.registry.read_text())['environments']
    targets = {name: configured[name] for name in TARGETS}
    with open(LOCK, 'a') as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.mode == 'plan':
            cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).timestamp()
            plan = inventory(targets, cutoff)
            with args.plan.open('x') as stream:
                json.dump({'cutoff': cutoff, 'plan': plan}, stream, indent=2)
            print('CLEANUP_PLAN', json.dumps({
                'old_backups': {target: len(paths) for target, paths in plan['old_backups'].items()},
                'completed_copies': len(plan['completed_copies']),
                'databases': sum(copy['exists'] for copy in plan['completed_copies']),
            }), flush=True)
        else:
            approved = json.loads(args.plan.read_text())
            result = apply(approved['plan'], targets, approved['cutoff'])
            args.plan.with_suffix('.result.json').write_text(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
