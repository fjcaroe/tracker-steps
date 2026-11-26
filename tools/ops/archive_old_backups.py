"""Archive explicit inactive backups to stdout, then prune only a verified copy.

No archive is staged on the server. Plans and receipts stay in the private
evidence directory; stdout in stream mode contains only tar.gz bytes.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import threading


ROOTS = (Path('/opt/backups'), Path('/opt/fernando_odoo18/backups'))
EVIDENCE = Path('/opt/steps-validation/server-cold-archive-20261126')
LOCK = '/run/lock/steps-environments.lock'
MAX_CUTOFF = '2026-11-01T00:00:00Z'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def managed():
    return importlib.import_module('cleanup_managed_copies')


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def atomic(path, value):
    temporary = path.with_name(path.name + '.tmp')
    require(not path.is_symlink() and not temporary.exists() and not temporary.is_symlink(),
            'unsafe or interrupted receipt')
    with temporary.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=True)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def evidence_path(path):
    require(path.is_absolute() and path.parent == EVIDENCE and path.suffix == '.json'
            and path.resolve() == path and not path.is_symlink(), 'unsafe evidence path')
    require(EVIDENCE.resolve() == EVIDENCE and EVIDENCE.is_dir(), 'unsafe evidence directory')
    return path


def cutoff_ns(value):
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    maximum = datetime.fromisoformat(MAX_CUTOFF.replace('Z', '+00:00'))
    require(stamp.tzinfo is not None and stamp <= maximum, 'cutoff must be no later than 2026-11-01')
    return int(stamp.timestamp() * 1_000_000_000)


def runtime_references():
    result = managed().runtime_references()
    nginx = Path('/etc/nginx')
    if nginx.is_dir():
        for path in nginx.rglob('*'):
            if path.is_file():
                result.append(path.read_text(errors='replace'))
    return result


def mount_paths():
    def unescape(value):
        return re.sub(r'\\([0-7]{3})', lambda match: chr(int(match[1], 8)), value)
    return [Path(unescape(line.split()[4]))
            for line in Path('/proc/self/mountinfo').read_text().splitlines()]


def source_root(path):
    require(path.is_absolute() and path.resolve() == path and not path.is_symlink(),
            'source must be a canonical absolute path')
    root = next((root for root in ROOTS if path.parent == root), None)
    require(root is not None and root.resolve() == root, 'source is not a direct child of a backup root')
    require(path.stat().st_dev == root.stat().st_dev, 'source crosses filesystems')
    return root


def identity(info):
    return {'size': info.st_size, 'mode': stat.S_IMODE(info.st_mode),
            'uid': info.st_uid, 'gid': info.st_gid, 'mtime_ns': info.st_mtime_ns,
            'ctime_ns': info.st_ctime_ns, 'device': info.st_dev, 'inode': info.st_ino}


def inspect(path, cutoff, references, mounts):
    root = source_root(path)
    require(not any(mount == path or mount.is_relative_to(path) for mount in mounts), 'mount inside source')
    require(not any(str(path) in reference for reference in references), 'source is referenced')
    entries, allocated, seen = [], 0, set()

    def visit(node):
        nonlocal allocated
        before = node.lstat()
        require(before.st_dev == root.stat().st_dev, 'foreign filesystem in source')
        require(stat.S_ISREG(before.st_mode) or stat.S_ISDIR(before.st_mode),
                'symlink or special file in source')
        require(before.st_mtime_ns < cutoff, 'source contains an item newer than cutoff')
        entry = dict(identity(before), path=node.relative_to(Path(node.anchor)).as_posix(),
                     type='directory' if stat.S_ISDIR(before.st_mode) else 'file')
        if entry['type'] == 'file':
            entry['sha256'] = digest(node)
        entries.append(entry)
        key = (before.st_dev, before.st_ino)
        if key not in seen:
            allocated += getattr(before, 'st_blocks', (before.st_size + 511) // 512) * 512
            seen.add(key)
        if entry['type'] == 'directory':
            for child in sorted(node.iterdir(), key=lambda child: child.name):
                visit(child)
        require(identity(node.lstat()) == identity(before), 'source changed during hashing')

    visit(path)
    fingerprint = hashlib.sha256(json.dumps(entries, sort_keys=True, ensure_ascii=True,
                                            separators=(',', ':')).encode()).hexdigest()
    return {'path': str(path), 'fingerprint': fingerprint, 'entries': entries}, allocated


def build_plan(paths, cutoff, references=None, mounts=None):
    require(paths and len(set(paths)) == len(paths), 'empty or duplicate selection')
    require(not any(a != b and a.is_relative_to(b) for a in paths for b in paths), 'overlapping selection')
    limit = cutoff_ns(cutoff)
    references = runtime_references() if references is None else references
    mounts = mount_paths() if mounts is None else mounts
    sources, allocated = [], 0
    for path in paths:
        row, amount = inspect(path, limit, references, mounts)
        sources.append(row)
        allocated += amount
    entries = [entry for source in sources for entry in source['entries']]
    require(len({entry['path'] for entry in entries}) == len(entries), 'duplicate archive member')
    return {'schema': 1, 'cutoff': cutoff, 'sources': sources,
            'logical_bytes': sum(entry['size'] for entry in entries if entry['type'] == 'file'),
            'allocated_bytes': allocated, 'entry_count': len(entries)}


def revalidate(plan):
    require(plan.get('schema') == 1, 'unsupported plan schema')
    fresh = build_plan([Path(source['path']) for source in plan['sources']], plan['cutoff'])
    require(fresh == plan, 'sources or selection changed since plan')


@contextmanager
def shared_lock():
    import fcntl
    with open(LOCK, 'a') as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def stream_archive(path, output):
    plan = load(path)
    receipt = path.with_suffix('.stream.json')
    require(not receipt.exists() and not receipt.is_symlink(), 'stream receipt already exists')
    revalidate(plan)
    members = [entry['path'] for source in plan['sources'] for entry in source['entries']]
    # Listing every entry requires --no-recursion to avoid duplicate members.
    names = b''.join(os.fsencode(name) + b'\0' for name in members)
    archive_hash, count = hashlib.sha256(), 0
    tar = gzip = writer = None
    writer_errors = []
    try:
        tar = subprocess.Popen(['tar', '-C', '/', '--format=pax', '--numeric-owner', '--acls', '--xattrs',
            '--hard-dereference', '--no-recursion', '--null', '--verbatim-files-from', '-cf', '-', '-T', '-'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr)
        gzip = subprocess.Popen(['gzip', '-1', '-n'], stdin=tar.stdout,
                                stdout=subprocess.PIPE, stderr=sys.stderr)
        tar.stdout.close()
        # The list can exceed a pipe buffer. Feed it while draining gzip so tar
        # cannot deadlock writing a large first file before reading later names.
        def feed_names():
            try:
                tar.stdin.write(names)
            except (OSError, ValueError) as error:
                writer_errors.append(error)
            finally:
                try:
                    tar.stdin.close()
                except (OSError, ValueError) as error:
                    writer_errors.append(error)
        writer = threading.Thread(target=feed_names, daemon=True)
        writer.start()
        for block in iter(lambda: gzip.stdout.read(8 * 1024 * 1024), b''):
            output.write(block)
            archive_hash.update(block)
            count += len(block)
        output.flush()
        gzip.stdout.close()
        gzip_exit, tar_exit = gzip.wait(), tar.wait()
        writer.join(timeout=10)
        require(not writer.is_alive() and not writer_errors and tar_exit == 0 and gzip_exit == 0,
                'tar or gzip failed')
        revalidate(plan)
        atomic(receipt, {'complete': True, 'plan_sha256': digest(path),
            'archive_sha256': archive_hash.hexdigest(), 'archive_bytes': count,
            'tar_exit': tar_exit, 'gzip_exit': gzip_exit})
    finally:
        for process in (tar, gzip):
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        if writer is not None:
            writer.join(timeout=10)
        for process in (tar, gzip):
            if process is not None and process.stdout is not None:
                process.stdout.close()


def verified_receipt(plan_path, local):
    remote = load(plan_path.with_suffix('.stream.json'))
    require(remote.get('complete') is True and remote.get('tar_exit') == 0
            and remote.get('gzip_exit') == 0 and remote.get('plan_sha256') == digest(plan_path),
            'stream did not complete for this plan')
    require(local.get('verified') is True, 'local archive is not verified')
    require(type(local.get('archive_bytes')) is int, 'invalid local archive size')
    for key in ('plan_sha256', 'archive_sha256', 'archive_bytes'):
        require(local.get(key) == remote.get(key), 'local receipt does not match stream: ' + key)
    require(type(remote.get('archive_bytes')) is int and remote['archive_bytes'] > 0
            and isinstance(remote.get('archive_sha256'), str)
            and re.fullmatch(r'[0-9a-f]{64}', remote['archive_sha256']),
            'invalid stream receipt')
    return remote


def free_bytes():
    disk = os.statvfs('/')
    return disk.f_bavail * disk.f_frsize


def prune(plan_path, receipt_path):
    plan, local = load(plan_path), load(receipt_path)
    remote = verified_receipt(plan_path, local)
    output = plan_path.with_suffix('.prune.json')
    require(not output.exists() and not output.is_symlink(), 'prune plan already consumed')
    revalidate(plan)
    result = {'complete': False, 'plan_sha256': digest(plan_path),
              'archive_sha256': remote['archive_sha256'], 'local_receipt_sha256': digest(receipt_path),
              'removed': [], 'in_progress': None,
              'free_bytes_before': free_bytes()}
    atomic(output, result)
    try:
        for source in plan['sources']:
            path = Path(source['path'])
            current, unused = inspect(path, cutoff_ns(plan['cutoff']), runtime_references(), mount_paths())
            require(current == source, 'source changed before removal')
            require(not any(str(path) in value for value in runtime_references()), 'source became referenced')
            result['in_progress'] = str(path)
            atomic(output, result)
            managed().remove_path(path, source_root(path))
            result['removed'].append(str(path))
            result['in_progress'] = None
            atomic(output, result)
        result['complete'] = True
    except Exception as error:
        result['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        result['free_bytes_after'] = free_bytes()
        atomic(output, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('plan', 'stream', 'prune'))
    parser.add_argument('plan', type=Path)
    parser.add_argument('--selection', type=Path)
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    require(not sys.flags.optimize and hasattr(os, 'geteuid') and os.geteuid() == 0
            and socket.gethostname().split('.')[0] == 'odoo-new', 'root on odoo-new without -O required')
    os.umask(0o077)
    require(EVIDENCE.parent.resolve() == EVIDENCE.parent, 'unsafe evidence root')
    EVIDENCE.mkdir(mode=0o700, exist_ok=True)
    evidence_path(args.plan)
    if args.mode == 'plan':
        require(args.selection is not None and args.receipt is None, 'plan requires only --selection')
        require(not args.plan.exists(), 'plan already exists')
        selection = load(evidence_path(args.selection))
        plan = build_plan([Path(path) for path in selection['paths']], selection['cutoff'])
        atomic(args.plan, plan)
        print(json.dumps({'sources': len(plan['sources']), 'entry_count': plan['entry_count'],
                          'logical_bytes': plan['logical_bytes'], 'allocated_bytes': plan['allocated_bytes']}))
    else:
        require(args.selection is None, '--selection is only valid for plan')
        with shared_lock():
            if args.mode == 'stream':
                require(args.receipt is None, '--receipt is only valid for prune')
                stream_archive(args.plan, sys.stdout.buffer)
            else:
                require(args.receipt is not None, 'prune requires --receipt')
                prune(args.plan, evidence_path(args.receipt))
                print(json.dumps({'complete': True, 'receipt': str(args.plan.with_suffix('.prune.json'))}))


if __name__ == '__main__':
    main()
