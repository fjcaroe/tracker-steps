"""Download an old-backup archive over pinned SSH, verify every byte, then retire it.

The remote helper streams directly to this machine. Nothing is extracted here;
source removal requires both the remote stream hash and full local tar validation.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import subprocess
import tarfile
import time


CHUNK = 1024 * 1024
ROOTS = {'/opt/backups', '/opt/fernando_odoo18/backups'}


def require(value, message):
    if not value:
        raise ValueError(message)


def digest_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(CHUNK), b''):
            digest.update(chunk)
    return digest.hexdigest()


def ssh_command(host, arguments):
    require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', host), 'invalid SSH alias')
    return ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'ConnectTimeout=15', host, shlex.join(arguments)]


def remote_read(host, path):
    result = subprocess.run(ssh_command(host, ['sudo', '-n', 'cat', '--', path]),
                            capture_output=True, check=False)
    require(result.returncode == 0, 'could not read remote verification metadata')
    return result.stdout


def write_new(path, data):
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def expected_members(plan):
    require(plan.get('schema') == 1 and plan.get('sources'), 'invalid archive plan')
    expected = {}
    for source in plan['sources']:
        source_path = PurePosixPath(source['path'])
        require(str(source_path.parent) in ROOTS and source_path.name not in ('', '.', '..'),
                'unexpected source root')
        prefix = str(source_path).lstrip('/')
        for entry in source['entries']:
            name = entry['path']
            path = PurePosixPath(name)
            require(not path.is_absolute() and '..' not in path.parts
                    and str(path) == name and '\x00' not in name,
                    'noncanonical archive member')
            require(name == prefix or name.startswith(prefix + '/'), 'member outside source')
            require(name not in expected and entry['type'] in ('file', 'directory'),
                    'duplicate member or unsupported type')
            require(isinstance(entry['size'], int) and entry['size'] >= 0,
                    'invalid expected member size')
            if entry['type'] == 'file':
                require(re.fullmatch(r'[0-9a-f]{64}', entry.get('sha256', '')),
                        'missing file checksum')
            expected[name] = entry
    require(len(expected) == plan['entry_count'], 'plan entry count mismatch')
    logical = sum(entry['size'] for entry in expected.values() if entry['type'] == 'file')
    require(logical == plan['logical_bytes'], 'plan logical size mismatch')
    return expected


def verify_archive(path, plan):
    expected = expected_members(plan)
    seen = set()
    files = total = 0
    # Streaming avoids extracting Linux paths or allocating a second local copy.
    with gzip.open(path, 'rb') as expanded:
        with tarfile.open(fileobj=expanded, mode='r|') as archive:
            for member in archive:
                name = member.name.rstrip('/')
                require(name in expected and name not in seen, 'extra or duplicate tar member')
                entry = expected[name]
                require((member.isdir() and entry['type'] == 'directory')
                        or (member.isfile() and entry['type'] == 'file'), 'tar member type mismatch')
                require(member.uid == entry['uid'] and member.gid == entry['gid']
                        and member.mode == entry['mode'], 'tar ownership or mode mismatch')
                mtime = Decimal(member.pax_headers.get('mtime', str(member.mtime)))
                require(int(mtime * 1_000_000_000) == entry['mtime_ns'], 'tar mtime mismatch')
                if member.isfile():
                    require(member.size == entry['size'], 'tar member size mismatch')
                    digest = hashlib.sha256()
                    actual = 0
                    stream = archive.extractfile(member)
                    require(stream is not None, 'missing tar payload')
                    for chunk in iter(lambda: stream.read(CHUNK), b''):
                        digest.update(chunk)
                        actual += len(chunk)
                    require(actual == entry['size'] and digest.hexdigest() == entry['sha256'],
                            'tar member content mismatch')
                    files += 1
                    total += actual
                seen.add(name)
        # tar ends before gzip does. Reading to EOF validates the gzip CRC/trailer.
        for chunk in iter(lambda: expanded.read(CHUNK), b''):
            require(not chunk.strip(b'\0'), 'unexpected payload after tar end')
    require(seen == set(expected), 'missing tar members')
    return {'files': files, 'entries': len(seen), 'logical_bytes': total}


def validate_stream_receipt(receipt, plan_sha, archive_sha, size):
    require(receipt.get('complete') is True and receipt.get('tar_exit') == 0
            and receipt.get('gzip_exit') == 0, 'remote archive did not finish cleanly')
    require(receipt.get('plan_sha256') == plan_sha
            and receipt.get('archive_sha256') == archive_sha
            and receipt.get('archive_bytes') == size, 'remote/local archive checksum mismatch')


def download(host, tool, plan_path, output, reserve_bytes, maximum_bytes, prune=False):
    output = output.absolute()
    require(output.name.endswith('.tar.gz') and output.parent.is_dir(), 'existing archive directory required')
    part = output.with_name(output.name + '.part')
    plan_copy = output.with_name(output.name + '.plan.json')
    receipt_path = output.with_name(output.name + '.verified.json')
    error_log = output.with_name(output.name + '.download.log')
    require(not any(p.exists() for p in [output, part, plan_copy, receipt_path, error_log]),
            'archive output or metadata already exists')
    raw_plan = remote_read(host, plan_path)
    plan = json.loads(raw_plan.decode('utf-8-sig'))
    expected_members(plan)
    estimate = plan['logical_bytes'] + plan['entry_count'] * 8192 + 16 * CHUNK
    require(estimate <= maximum_bytes, 'archive batch exceeds selected maximum')
    require(shutil.disk_usage(output.parent).free >= estimate + reserve_bytes,
            'insufficient local space for batch plus reserve')
    plan_sha = hashlib.sha256(raw_plan).hexdigest()
    write_new(plan_copy, raw_plan)
    arguments = ['sudo', '-n', 'ionice', '-c3', 'nice', '-n', '19',
                 'python3.10', tool, 'stream', plan_path]
    digest = hashlib.sha256()
    downloaded = 0
    report_at = time.monotonic() + 15
    process = None
    try:
        with error_log.open('xb') as errors, part.open('xb') as archive:
            process = subprocess.Popen(ssh_command(host, arguments), stdout=subprocess.PIPE,
                                       stderr=errors)
            for chunk in iter(lambda: process.stdout.read(CHUNK), b''):
                require(downloaded + len(chunk) <= maximum_bytes, 'archive stream exceeded size limit')
                require(shutil.disk_usage(output.parent).free >= reserve_bytes + len(chunk),
                        'local disk reserve reached')
                archive.write(chunk)
                digest.update(chunk)
                downloaded += len(chunk)
                if time.monotonic() >= report_at:
                    print('DOWNLOADED_MIB', round(downloaded / CHUNK), flush=True)
                    report_at = time.monotonic() + 15
            require(process.wait() == 0, 'remote stream failed; source files preserved')
            archive.flush()
            os.fsync(archive.fileno())
        archive_sha = digest.hexdigest()
        stream_path = str(PurePosixPath(plan_path).with_suffix('.stream.json'))
        remote_receipt = json.loads(remote_read(host, stream_path).decode('utf-8-sig'))
        validate_stream_receipt(remote_receipt, plan_sha, archive_sha, downloaded)
        require(digest_file(part) == archive_sha, 'local archive changed after download')
        checked = verify_archive(part, plan)
        # Exclusive hard-link promotion cannot overwrite another file on Windows or Linux.
        os.link(part, output)
        part.unlink()
        receipt = {'verified': True, 'verified_utc': datetime.now(timezone.utc).isoformat(),
                   'host': host, 'plan_sha256': plan_sha, 'archive_sha256': archive_sha,
                   'archive_bytes': downloaded, 'local_archive': str(output), **checked}
        receipt_bytes = json.dumps(receipt, indent=2).encode('utf-8')
        write_new(receipt_path, receipt_bytes)
        print('ARCHIVE_VERIFIED', json.dumps(receipt), flush=True)
        if prune:
            # Confirm the promoted, durable file still matches immediately before authorization.
            require(digest_file(output) == archive_sha, 'verified local archive changed before retirement')
            remote_receipt_path = str(PurePosixPath(plan_path).with_suffix('.local-receipt.json'))
            upload = subprocess.run(ssh_command(host, ['sudo', '-n', 'python3.10', '-c',
                'import os,pathlib,sys;os.umask(0o077);p=pathlib.Path(sys.argv[1]);'
                'f=p.open("xb");f.write(sys.stdin.buffer.read());f.flush();os.fsync(f.fileno());f.close()',
                remote_receipt_path]), input=receipt_bytes, capture_output=True)
            require(upload.returncode == 0, 'could not record local verification on server')
            command = ['sudo', '-n', 'ionice', '-c3', 'nice', '-n', '19', 'python3.10',
                       tool, 'prune', plan_path, '--receipt', remote_receipt_path]
            result = subprocess.run(ssh_command(host, command), capture_output=True)
            write_new(output.with_name(output.name + '.retirement.log'), result.stdout + result.stderr)
            require(result.returncode == 0, 'source retirement needs review; local archive is safe')
            print('REMOTE_RETIREMENT_COMPLETED', output.name, flush=True)
        return receipt
    except BaseException:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        # Only this invocation's incomplete temporary output is disposable.
        if part.exists():
            part.unlink()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='odoo-new')
    parser.add_argument('--remote-tool', required=True)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--reserve-gib', default=10, type=int)
    parser.add_argument('--max-gib', default=8, type=int)
    parser.add_argument('--prune', action='store_true')
    args = parser.parse_args()
    require(args.reserve_gib >= 10 and 0 < args.max_gib <= 10, 'invalid local space bounds')
    download(args.host, args.remote_tool, args.plan, args.output,
             args.reserve_gib * 1024 ** 3, args.max_gib * 1024 ** 3, args.prune)


if __name__ == '__main__':
    main()
