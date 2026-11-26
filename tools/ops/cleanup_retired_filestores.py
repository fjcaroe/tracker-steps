"""Remove only orphan filestores of the 180 private databases retired on 2026-11-23.

Keeps source dumps, QA certificates, code, logs and every PostgreSQL database.
Run plan/apply as root on odoo-new, preferably with ionice -c3 nice -n19.
Snapshot proof is the raw JSON array from gcloud compute snapshots list,
containing name, status, id, sourceDisk and creationTimestamp for today's disks.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import sys

import cleanup_managed_copies as managed


ROOT = Path('/opt/steps-validation')
HISTORY = ROOT / 'server-disk-cleanup-20261123/managed-review.result.json'
HISTORY_SHA = '3a2fd28df781e4c7fcd3e89266f209fb1a30cdd86727055fd0302570ccf6d2ca'
DISKS = {
    'odoo-new-disk': 'root',
    'odoo-data-balanced-20260923': 'data',
}
DISK_PREFIX = 'https://www.googleapis.com/compute/v1/projects/stepsconsulting/zones/us-central1-c/disks/'


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def safe(path, root=None):
    root = ROOT if root is None else root
    require(path.is_absolute() and path != root and path.is_relative_to(root), 'outside allowed root')
    require(path.resolve() == path and not path.is_symlink(), 'symlink or unresolved path')
    require(path.stat().st_dev == root.stat().st_dev == Path('/').stat().st_dev, 'not root filesystem')
    return path


def atomic(path, value):
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('x', encoding='utf-8') as output:
        json.dump(value, output, indent=2)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def snapshots(path, now=None):
    safe(path)
    now = now or datetime.now(timezone.utc)
    rows = load(path)
    require(isinstance(rows, list) and len(rows) == 2, 'need both disk snapshots')
    stamps = {}
    for row in rows:
        disk = row.get('sourceDisk', '').removeprefix(DISK_PREFIX)
        require(disk in DISKS and row['sourceDisk'] == DISK_PREFIX + disk, 'unexpected snapshot source')
        require(disk not in stamps and row.get('status') == 'READY' and str(row.get('id', '')).isdigit(),
                'snapshot not READY or duplicated')
        stamp = datetime.fromisoformat(row['creationTimestamp'].replace('Z', '+00:00'))
        require(stamp.tzinfo is not None and stamp.astimezone(timezone.utc).date() == now.date()
                and stamp <= now, 'snapshot must be from today')
        stamps[disk] = stamp.timestamp()
    require(set(stamps) == set(DISKS), 'missing disk snapshot')
    return {'path': str(path), 'sha256': managed.fingerprint(path, 'sha256'), 'snapshots': rows,
            'root_capture_ns': int(stamps['odoo-new-disk'] * 1_000_000_000)}


def mount_paths():
    return [Path(line.split()[4].replace('\\040', ' '))
            for line in Path('/proc/self/mountinfo').read_text().splitlines()]


def tree(path, capture_ns):
    safe(path)
    device = path.stat().st_dev
    digest = hashlib.sha256()
    totals = {'entries': 0, 'bytes': 0, 'reclaimable_bytes': 0}
    # scandir never follows links; the tuple also detects changed inodes/metadata.
    def visit(node):
        current = node.lstat()
        require(current.st_dev == device and not stat.S_ISLNK(current.st_mode), 'symlink or foreign device')
        require(stat.S_ISDIR(current.st_mode) or stat.S_ISREG(current.st_mode), 'special file')
        require(max(current.st_mtime_ns, current.st_ctime_ns) <= capture_ns, 'newer than root snapshot')
        identity = (str(node.relative_to(path)), current.st_dev, current.st_ino,
                    current.st_mode, current.st_size, current.st_mtime_ns,
                    current.st_ctime_ns, current.st_nlink,
                    getattr(current, 'st_blocks', (current.st_size + 511) // 512))
        digest.update((json.dumps(identity, ensure_ascii=True) + '\n').encode())
        totals['entries'] += 1
        if stat.S_ISREG(current.st_mode):
            totals['bytes'] += current.st_size
            if current.st_nlink == 1:
                totals['reclaimable_bytes'] += identity[-1] * 512
        else:
            for entry in sorted(node.iterdir(), key=lambda entry: entry.name):
                visit(entry)
    visit(path)
    require(not any(mount == path or mount.is_relative_to(path) for mount in mount_paths()), 'mount inside target')
    return dict(totals, sha256=digest.hexdigest())


def retired():
    safe(HISTORY)
    require(managed.fingerprint(HISTORY, 'sha256') == HISTORY_SHA, 'historical receipt changed')
    rows = load(HISTORY)['retired_databases']
    require(len(rows) == 180 and len({row['database'] for row in rows}) == 180, 'unexpected historical retirement set')
    return {row['database']: row for row in rows}


def databases():
    return set(managed.read_sql('postgres', 'SELECT datname FROM pg_database'))


def candidate(row, existing, references, proof):
    database = row['database']
    require(re.fullmatch(r'MANAGEMENT_QA_[A-Z-]+_[a-z0-9_]{1,24}', database), 'not a private database')
    require(database not in existing, 'database still exists')
    source = safe(Path(row['retained_source']['path']))
    require(source.name == 'source.dump' and source.is_file(), 'unexpected source dump')
    stage = safe(source.parent)
    require(stage.parent == ROOT and re.fullmatch(r'management_[a-z-]+_[a-z0-9_]{1,24}', stage.name),
            'unexpected validation stage')
    certificate = safe(stage / 'qa_passed.json')
    qa = load(certificate)
    require(qa.get('database') == database and re.fullmatch(r'[0-9a-f]{40}', qa.get('commit', '')),
            'QA certificate database mismatch')
    require(source.stat().st_size == row['retained_source']['bytes']
            and managed.fingerprint(source, 'sha256') == row['retained_source']['sha256'], 'source dump changed')
    data = safe(stage / 'data')
    base = safe(data / 'filestore')
    path = safe(base / database)
    require(path.is_dir(), 'filestore missing')
    # A parent data_dir or the private DB itself in a service/process is also protected.
    require(not managed.referenced(references, str(data), database), 'runtime/config reference')
    return {'database': database, 'path': str(path),
            'source_sha256': row['retained_source']['sha256'],
            'qa_sha256': managed.fingerprint(certificate, 'sha256'),
            'tree': tree(path, proof['root_capture_ns'])}


def free_bytes():
    return os.statvfs('/').f_bavail * os.statvfs('/').f_frsize


def plan(output, snapshot_path, limit):
    require(not output.exists(), 'plan already exists')
    history = retired()
    proof = snapshots(snapshot_path)
    existing, references = databases(), managed.runtime_references()
    result = {'schema': 1, 'history_sha256': HISTORY_SHA, 'snapshot_proof': proof,
              'candidates': [], 'skipped': []}
    for database, row in history.items():
        if limit and len(result['candidates']) >= limit:
            break
        try:
            result['candidates'].append(candidate(row, existing, references, proof))
        except (ValueError, OSError, KeyError) as error:
            result['skipped'].append({'database': database, 'reason': str(error)})
        print('INVENTORIED', database, flush=True)
    atomic(output, result)
    print('PLAN_READY', json.dumps({'candidates': len(result['candidates']), 'skipped': len(result['skipped']),
          'reclaimable_bytes': sum(item['tree']['reclaimable_bytes'] for item in result['candidates'])}), flush=True)


def apply(output, snapshot_path):
    safe(output)
    approved = load(output)
    require(approved.get('schema') == 1 and approved.get('history_sha256') == HISTORY_SHA, 'invalid plan')
    history = retired()
    proof = snapshots(snapshot_path)
    require(proof == approved['snapshot_proof'], 'snapshot proof changed')
    receipt = output.with_suffix('.result.json')
    require(not receipt.exists(), 'plan already consumed')
    rows = approved['candidates']
    require(rows and len({row['database'] for row in rows}) == len(rows), 'empty or duplicate plan')
    result = {'plan_sha256': managed.fingerprint(output, 'sha256'), 'before_free_bytes': free_bytes(),
              'removed': [], 'in_progress': None, 'complete': False}
    atomic(receipt, result)
    try:
        for item in rows:
            database = item['database']
            require(database in history, 'database not in historical receipt')
            fresh = candidate(history[database], databases(), managed.runtime_references(), proof)
            require(fresh == item, 'candidate changed since plan')
            require(database not in databases(), 'database appeared before removal')
            require(not managed.referenced(managed.runtime_references(),
                    str(Path(item['path']).parent.parent), database),
                    'runtime/config reference appeared before removal')
            result['in_progress'] = item['path']
            atomic(receipt, result)
            managed.remove_path(Path(item['path']), ROOT)
            result['removed'].append(item)
            result['in_progress'] = None
            result['after_free_bytes'] = free_bytes()
            atomic(receipt, result)
            print('REMOVED_ORPHAN_FILESTORE', database, flush=True)
        result['complete'] = True
    except Exception as error:
        result['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        result['after_free_bytes'] = free_bytes()
        atomic(receipt, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('plan', 'apply'))
    parser.add_argument('plan', type=Path)
    parser.add_argument('--snapshots', required=True, type=Path)
    parser.add_argument('--limit', default=0, type=int, help='plan at most N candidates; 0 means all')
    args = parser.parse_args()
    require(not sys.flags.optimize and os.geteuid() == 0
            and socket.gethostname().split('.')[0] == 'odoo-new', 'root on odoo-new required')
    require(args.limit >= 0, 'negative limit')
    safe(args.plan.parent)
    require(args.plan.resolve() == args.plan and not args.plan.is_symlink(), 'unsafe plan path')
    os.umask(0o077)
    with open(managed.LOCK, 'a') as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.mode == 'plan':
            plan(args.plan, args.snapshots, args.limit)
        else:
            require(args.limit == 0, 'limit applies only to plan')
            apply(args.plan, args.snapshots)


if __name__ == '__main__':
    main()
