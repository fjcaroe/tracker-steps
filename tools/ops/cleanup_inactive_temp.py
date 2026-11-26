"""Plan and retire explicit, old, inactive Steps build directories.

Whole directories must be direct /var/tmp/steps-* children and clean Git clones
whose HEAD is already represented by remote refs. Generated node_modules,
.venv/venv, or recognized Playwright browsers may be selected below those
children; the source tree and its lock/requirements files are preserved.
Plans contain filesystem identities, never shell commands. No Odoo database,
configuration, release, live log, or service is changed.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import socket
import stat
import subprocess
import time


TEMP_ROOT = Path('/var/tmp')
EVIDENCE_ROOT = Path('/opt/steps-validation')
LOCK = '/run/lock/steps-environments.lock'
MIN_AGE_SECONDS = 7 * 24 * 3600
NAME = re.compile(r'steps-[A-Za-z0-9][A-Za-z0-9_.-]*')
EVIDENCE_NAME = re.compile(r'server-disk-cleanup-[A-Za-z0-9][A-Za-z0-9_.-]*')
DEPENDENCIES = {'node_modules', '.venv', 'venv'}
BROWSER_REVISION = re.compile(r'(chromium|chromium_headless_shell|ffmpeg|firefox|webkit)-[0-9]+')
IGNORED_BUILD = DEPENDENCIES | {'dist', 'build', '.cache', '.vite', '__pycache__',
    '.pytest_cache', '.mypy_cache', 'coverage', '.next', '.nuxt', '.turbo'}


class UnsafeCandidate(ValueError):
    pass


def managed():
    # Lazy import leaves the filesystem checks testable on Windows, where the
    # existing Linux-only helper imports fcntl. The executable still requires it.
    return importlib.import_module('cleanup_managed_copies')


def runtime_references():
    references = managed().runtime_references()
    # sudo and the invoking shell retain our explicit candidate arguments while
    # waiting for this process. Exclude only their exact invocation cmdlines;
    # their cwd/descriptors, and every unrelated process, remain protected.
    parent = os.getpid()
    seen = set()
    while parent > 1 and parent not in seen:
        seen.add(parent)
        try:
            status = (Path('/proc') / str(parent) / 'status').read_text()
            parent = int(re.search(r'^PPid:\s+(\d+)$', status, re.M)[1])
            command = (Path('/proc') / str(parent) / 'cmdline').read_text(errors='replace')
        except (OSError, TypeError, ValueError):
            break
        if Path(__file__).name in command and command in references:
            references.remove(command)
    nginx = Path('/etc/nginx')
    if nginx.exists():
        for path in nginx.rglob('*'):
            if path.is_file():
                references.append(path.read_text(errors='replace'))
    return references


def mount_paths():
    def unescape(value):
        return re.sub(r'\\([0-7]{3})', lambda match: chr(int(match[1], 8)), value)
    return [Path(unescape(line.split()[4]))
            for line in Path('/proc/self/mountinfo').read_text().splitlines()]


def candidate_path(path, root=TEMP_ROOT):
    if not path.is_absolute() or root.resolve() != root or path.resolve() != path:
        raise UnsafeCandidate('absolute, canonical, non-symlink path required')
    if path.parent == root and NAME.fullmatch(path.name):
        project, kind = path, 'clean_clone'
    elif (path.name in DEPENDENCIES | {'browsers'} and path.parent.parent == root
          and NAME.fullmatch(path.parent.name)):
        project = path.parent
        kind = 'browser_cache' if path.name == 'browsers' else 'dependencies'
    else:
        raise UnsafeCandidate('outside explicit Steps temporary build scope')
    if (project.is_symlink() or not project.is_dir() or path.is_symlink()
            or not path.is_dir() or path.stat().st_dev != root.stat().st_dev):
        raise UnsafeCandidate('real directories on the temporary filesystem required')
    if kind != 'clean_clone':
        if path.name in {'node_modules', 'browsers'}:
            markers = [project / 'package-lock.json', project / 'npm-shrinkwrap.json']
        else:
            markers = list(project.glob('requirements*.txt'))
        if not any(marker.is_file() and not marker.is_symlink()
                   and marker.resolve().parent == project for marker in markers):
            raise UnsafeCandidate('dependency lock or requirements file missing')
        if kind == 'browser_cache':
            revisions = 0
            for child in path.iterdir():
                if (child.is_symlink() or not child.is_dir()
                        or not (child.name == '.links' or BROWSER_REVISION.fullmatch(child.name))):
                    raise UnsafeCandidate('browser cache contains an unrecognized entry')
                revisions += bool(BROWSER_REVISION.fullmatch(child.name))
            if not revisions:
                raise UnsafeCandidate('browser cache has no recognized Playwright revision')
    return project, kind


def clean_git(path):
    gitdir = path / '.git'
    if not gitdir.is_dir() or gitdir.is_symlink():
        raise UnsafeCandidate('whole directory is not an independent Git clone')
    command = ['git', '--no-optional-locks', '--no-replace-objects',
               '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=/dev/null', '-C', str(path)]
    environment = dict(os.environ, GIT_NO_LAZY_FETCH='1', GIT_TERMINAL_PROMPT='0',
                       GIT_ALLOW_PROTOCOL='')
    result = subprocess.run([*command, 'status', '--porcelain=v1',
        '-z', '--untracked-files=all', '--ignore-submodules=none', '--ignored=matching'],
        capture_output=True, timeout=60, check=False, env=environment)
    if result.returncode:
        raise UnsafeCandidate('Git status could not establish a clean source tree')
    for entry in result.stdout.split(b'\0'):
        if not entry:
            continue
        if not entry.startswith(b'!! '):
            raise UnsafeCandidate('Git source tree has tracked or untracked changes')
        name = Path(os.fsdecode(entry[3:]).rstrip('/'))
        if not any(part in IGNORED_BUILD for part in name.parts):
            raise UnsafeCandidate('ignored file is not a recognized build artifact')
    published = subprocess.run([*command, 'rev-list', '--count', 'HEAD', '--not', '--remotes'],
        capture_output=True, timeout=60, check=False, env=environment)
    if published.returncode or published.stdout.strip() != b'0':
        raise UnsafeCandidate('Git HEAD contains commits not represented by remote refs')


def identity(info):
    return {'device': info.st_dev, 'inode': info.st_ino, 'mode': info.st_mode,
            'size': info.st_size, 'mtime_ns': info.st_mtime_ns,
            'ctime_ns': info.st_ctime_ns}


def inspect(path, cutoff, references, mounts, root=TEMP_ROOT):
    project, kind = candidate_path(path, root)
    if any(mount == path or mount.is_relative_to(path) for mount in mounts):
        raise UnsafeCandidate('candidate contains a mount point')
    # A process/config using the project may load a dependency lazily, even if no
    # descriptor currently points into node_modules or the virtual environment.
    if any(str(project) in reference for reference in references):
        raise UnsafeCandidate('project is referenced by a process or configuration')
    if kind == 'clean_clone':
        clean_git(path)
    before = identity(path.lstat())
    device = root.stat().st_dev
    digest = hashlib.sha256()
    entries = files = total = allocated = 0
    pending = [path]
    while pending:
        item = pending.pop()
        info = item.lstat()
        if info.st_dev != device:
            raise UnsafeCandidate('candidate crosses filesystems')
        if info.st_mtime > cutoff:
            raise UnsafeCandidate('candidate contains an item newer than seven days')
        if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)
                or stat.S_ISLNK(info.st_mode)):
            raise UnsafeCandidate('candidate contains a special file')
        record = [str(item.relative_to(path)), identity(info)]
        if stat.S_ISLNK(info.st_mode):
            record.append(os.readlink(item))
        elif stat.S_ISDIR(info.st_mode):
            with os.scandir(item) as children:
                pending.extend(sorted((Path(child.path) for child in children), reverse=True))
        else:
            files += 1
            total += info.st_size
            allocated += getattr(info, 'st_blocks', (info.st_size + 511) // 512) * 512
        digest.update(json.dumps(record, sort_keys=True).encode('utf-8', errors='surrogateescape'))
        digest.update(b'\n')
        entries += 1
    if identity(path.lstat()) != before:
        raise UnsafeCandidate('candidate changed during inventory')
    return {'path': str(path), 'project': str(project), 'kind': kind,
            'identity': before, 'tree_sha256': digest.hexdigest(),
            'entries': entries, 'files': files, 'bytes': total,
            'allocated_bytes': allocated}


def make_plan(paths, cutoff, references, mounts, root=TEMP_ROOT):
    paths = list(dict.fromkeys(paths))
    if any(first != second and first.is_relative_to(second)
           for first in paths for second in paths):
        raise UnsafeCandidate('overlapping candidates are not allowed')
    plan = {'schema': 1, 'created_utc': datetime.now(timezone.utc).isoformat(),
            'cutoff': cutoff, 'minimum_age_days': 7, 'candidates': [], 'skipped': []}
    for path in paths:
        try:
            plan['candidates'].append(inspect(path, cutoff, references, mounts, root))
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            plan['skipped'].append({'path': str(path), 'reason': str(error)})
    return plan


def evidence_path(path, root=EVIDENCE_ROOT):
    if (not path.is_absolute() or path.resolve() != path or path.parent.parent != root
            or not EVIDENCE_NAME.fullmatch(path.parent.name) or path.suffix != '.json'
            or path.is_symlink() or root.resolve() != root):
        raise UnsafeCandidate('plan must be JSON directly inside an approved cleanup evidence directory')
    return path


def atomic_json(path, value):
    temporary = path.with_name(path.name + '.tmp')
    if path.is_symlink() or temporary.exists() or temporary.is_symlink():
        raise UnsafeCandidate('unsafe or interrupted receipt path')
    with temporary.open('x', encoding='utf-8') as output:
        json.dump(value, output, indent=2)
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(path)


def apply_plan(plan, receipt, root=TEMP_ROOT, collect=runtime_references,
               mounts=mount_paths, remove=None):
    if (plan.get('schema') != 1 or plan.get('minimum_age_days') != 7
            or not isinstance(plan.get('cutoff'), (int, float))
            or not math.isfinite(plan['cutoff'])
            or plan['cutoff'] > time.time() - MIN_AGE_SECONDS):
        raise UnsafeCandidate('invalid or insufficiently old cleanup plan')
    if receipt.exists() or receipt.is_symlink():
        raise UnsafeCandidate('plan already applied or unsafe receipt path')
    candidates = plan['candidates']
    paths = [Path(candidate['path']) for candidate in candidates]
    if len(paths) != len(set(paths)) or any(first != second and first.is_relative_to(second)
            for first in paths for second in paths):
        raise UnsafeCandidate('duplicate or overlapping planned candidates')
    result = {'started_utc': datetime.now(timezone.utc).isoformat(),
              'removed': [], 'skipped': [], 'free_bytes_before': shutil.disk_usage(root).free}
    atomic_json(receipt, result)
    for candidate in candidates:
        path = Path(candidate['path'])
        try:
            current = inspect(path, plan['cutoff'], collect(), mounts(), root)
            if current != candidate:
                raise UnsafeCandidate('filesystem identity or contents changed since plan')
            # Refresh process/config references immediately before deletion.
            if any(str(path.parent if current['kind'] != 'clean_clone' else path) in value
                   for value in collect()):
                raise UnsafeCandidate('project became referenced before deletion')
            if identity(path.lstat()) != candidate['identity']:
                raise UnsafeCandidate('candidate identity changed before deletion')
            (remove or managed().remove_path)(path, root)
            result['removed'].append(candidate)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            result['skipped'].append({'path': str(path), 'reason': str(error)})
        result['free_bytes_after'] = shutil.disk_usage(root).free
        atomic_json(receipt, result)
    result['finished_utc'] = datetime.now(timezone.utc).isoformat()
    atomic_json(receipt, result)
    return result


@contextmanager
def shared_lock():
    import fcntl
    with open(LOCK, 'a') as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('plan', 'apply'))
    parser.add_argument('plan', type=Path)
    parser.add_argument('paths', nargs='*', type=Path)
    args = parser.parse_args()
    if not hasattr(os, 'geteuid') or os.geteuid() != 0 or socket.gethostname().split('.')[0] != 'odoo-new':
        parser.error('run only as root on odoo-new')
    if (args.mode == 'plan') != bool(args.paths):
        parser.error('plan requires explicit candidates; apply accepts only the saved plan')
    os.umask(0o077)
    plan_path = evidence_path(args.plan)
    with shared_lock():
        if args.mode == 'plan':
            plan_path.parent.mkdir(mode=0o700, exist_ok=True)
            plan = make_plan(args.paths, time.time() - MIN_AGE_SECONDS,
                             runtime_references(), mount_paths())
            with plan_path.open('x', encoding='utf-8') as output:
                json.dump(plan, output, indent=2)
            print(json.dumps({'candidates': len(plan['candidates']),
                'skipped': plan['skipped'], 'allocated_bytes': sum(
                    item['allocated_bytes'] for item in plan['candidates'])}))
        else:
            plan = json.loads(plan_path.read_text(encoding='utf-8'))
            result = apply_plan(plan, plan_path.with_suffix('.result.json'))
            print(json.dumps({'removed': len(result['removed']), 'skipped': result['skipped'],
                'free_bytes_before': result['free_bytes_before'],
                'free_bytes_after': result.get('free_bytes_after', result['free_bytes_before'])}))


if __name__ == '__main__':
    main()
