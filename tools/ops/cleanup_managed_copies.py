"""Retire reviewed, recoverable managed Odoo backups and private copies."""
import argparse
import configparser
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
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
POSTGRES = ('sudo', '-n', '-u', 'postgres')


def psql(database):
    return (*POSTGRES, 'env', 'PGOPTIONS=-c default_transaction_read_only=on',
            'psql', '-XqAt', '-v', 'ON_ERROR_STOP=1', '-d', database)


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
    retained_backups = {}
    for name, paths in groups.items():
        retained_backups[name] = [str(path) for path in paths[-2:]]
        old = [str(path) for path in paths[:-2] if path.stat().st_mtime < cutoff
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
        if (database not in existing or proof.get('database') != database
                or not isinstance(commit, str) or not COMMIT.fullmatch(commit)
                or commit not in published[target]
                or proof_path.stat().st_mtime >= cutoff or stage.stat().st_mtime >= cutoff
                or database in protected or database in active or referenced(references, str(stage), database)):
            continue
        release = manifest(RELEASES / target / commit / 'release.json')
        if release.get('commit') != commit:
            continue
        dump = stage / 'source.dump'
        if dump.is_file() and local_path(dump, VALIDATION):
            copies.append({'target': target, 'database': database, 'stage': str(stage), 'dump': str(dump)})
    return {'old_backups': backups, 'retained_backups': retained_backups, 'completed_copies': copies}


def fingerprint(path, algorithm):
    digest = hashlib.new(algorithm)
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def verify_dump(dump, root, database):
    assert dump.is_file() and local_path(dump, root)
    toc = subprocess.check_output(['pg_restore', '--list', str(dump)], text=True)
    assert re.search(r'^;\s+dbname:\s*' + re.escape(database) + r'\s*$', toc, re.M)
    subprocess.run(['pg_restore', '--exit-on-error', '--file=/dev/null', str(dump)], check=True)
    return {'path': str(dump), 'sha256': fingerprint(dump, 'sha256'), 'bytes': dump.stat().st_size}


def attachment_files(dump):
    command = ['pg_restore', '--exit-on-error', '--data-only', '--table=ir_attachment',
               '--file=-', str(dump)]
    names = set()
    column = None
    with subprocess.Popen(command, stdout=subprocess.PIPE) as process:
        for line in process.stdout:
            if line.startswith(b'COPY public.ir_attachment ('):
                column = line.split(b'(', 1)[1].split(b')', 1)[0].split(b', ').index(b'store_fname')
            elif column is not None:
                if line.rstrip(b'\n') == b'\\.':
                    break
                value = line.rstrip(b'\n').split(b'\t', column + 1)[column]
                if value not in (b'', b'\\N'):
                    names.add(value.decode('ascii'))
        # Drain the small pg_restore footer before waiting on the child.
        for unused in process.stdout:
            pass
        assert process.wait() == 0 and column is not None
    assert all(ATTACHMENT.fullmatch(name) for name in names)
    return names


def verify_retained_backup(path, database):
    filestore = path / 'filestore'
    assert filestore.is_dir() and local_path(filestore, BACKUPS)
    dump = path / 'database.dump'
    result = verify_dump(dump, BACKUPS, database)
    names = attachment_files(dump)
    for name in names:
        attachment = filestore / name
        assert attachment.is_file() and local_path(attachment, filestore)
        assert fingerprint(attachment, 'sha1') == attachment.name
    return dict(result, referenced_filestore_files=len(names))


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
    pgdata, = read_sql('postgres', 'SHOW data_directory')
    return {key: disk.f_bavail * disk.f_frsize for key, disk in
            [('root', os.statvfs('/')), ('postgres', os.statvfs(pgdata))]}


def apply(plan, targets, cutoff, receipt):
    current = inventory(targets, cutoff)
    before = free_bytes()
    result = {'before': before, 'removed_backups': [], 'retired_databases': [],
              'retained_backups': {}, 'skipped': []}

    def save():
        result['after'] = free_bytes()
        temporary = receipt.with_suffix('.tmp')
        temporary.write_text(json.dumps(result, indent=2))
        temporary.replace(receipt)

    references = runtime_references()
    for copy in plan['completed_copies']:
        database = copy['database']
        if copy not in current['completed_copies'] or referenced(references, copy['stage'], database):
            result['skipped'].append({'database': database, 'reason': 'changed or in use'})
            continue
        try:
            backup = verify_dump(Path(copy['dump']), VALIDATION, targets[copy['target']]['database'])
            subprocess.run([*POSTGRES, 'dropdb', '--', database], check=True)
        except (AssertionError, OSError, subprocess.CalledProcessError) as error:
            result['skipped'].append({'database': database, 'reason': type(error).__name__})
            continue
        result['retired_databases'].append({'database': database, 'retained_source': backup})
        save()
        if len(result['retired_databases']) % 20 == 0:
            print('PRIVATE_DATABASES_RETIRED', len(result['retired_databases']), flush=True)
    references = runtime_references()
    for target, paths in plan['old_backups'].items():
        protected = current['retained_backups'][target]
        try:
            assert len(protected) == 2
            result['retained_backups'][target] = [
                verify_retained_backup(Path(name), targets[target]['database']) for name in protected]
        except (AssertionError, OSError, ValueError, subprocess.CalledProcessError) as error:
            result['skipped'].append({'target': target, 'reason': 'retained backup: ' + type(error).__name__})
            continue
        for name in paths:
            if name not in current['old_backups'].get(target, ()) or referenced(references, name):
                result['skipped'].append({'backup': name, 'reason': 'changed or in use'})
                continue
            remove_path(Path(name), BACKUPS)
            result['removed_backups'].append(name)
            save()
    save()
    print('CLEANUP_DONE', json.dumps({'retired_databases': len(result['retired_databases']),
        'removed_backups': len(result['removed_backups']), 'skipped': len(result['skipped']),
        'before': before, 'after': result['after']}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('plan', 'apply'))
    parser.add_argument('plan', type=Path)
    parser.add_argument('--registry', type=Path, required=True)
    args = parser.parse_args()
    assert os.geteuid() == 0 and socket.gethostname().split('.')[0] == 'odoo-new'
    assert args.plan.is_absolute() and args.plan.resolve().is_relative_to(VALIDATION)
    os.umask(0o077)
    configured = json.loads(args.registry.read_text())['environments']
    targets = {name: configured[name] for name in TARGETS}
    with open(LOCK, 'a') as lease:
        if args.mode == 'plan':
            cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).timestamp()
            plan = inventory(targets, cutoff)
            with args.plan.open('x') as stream:
                json.dump({'cutoff': cutoff, 'plan': plan}, stream, indent=2)
            print('CLEANUP_PLAN', json.dumps({
                'old_backups': {target: len(paths) for target, paths in plan['old_backups'].items()},
                'completed_copies': len(plan['completed_copies']),
            }), flush=True)
        else:
            receipt = args.plan.with_suffix('.result.json')
            print('WAITING_FOR_SHARED_ENVIRONMENT_LOCK', flush=True)
            fcntl.flock(lease, fcntl.LOCK_EX)
            assert not receipt.exists(), 'This plan was already used'
            approved = json.loads(args.plan.read_text())
            apply(approved['plan'], targets, approved['cutoff'], receipt)


if __name__ == '__main__':
    main()
