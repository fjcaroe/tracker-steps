"""Approved 100 -> 150 GiB capacity change for the documented shared data disk.

Requires explicit human authorization. No database DML, service restart,
credential change, partition change or deletion. Keep all backup artifacts.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

PROJECT = 'stepsconsulting'
ZONE = 'us-central1-c'
DISK = 'odoo-data-balanced-20260923'
DEVICE = Path('/dev/disk/by-id/google-' + DISK)
ROOT = Path('/opt/steps-validation/community-payroll-disk-resize-20261028')
INSTANCE = 'https://www.googleapis.com/compute/v1/projects/stepsconsulting/zones/us-central1-c/instances/odoo-new'


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply-approved', action='store_true', required=True)
    args = parser.parse_args()
    assert args.apply_approved and os.geteuid() == 0
    actor = os.environ.get('SUDO_USER')
    assert actor and actor != 'root'
    gcloud = shutil.which('gcloud')
    assert gcloud and DEVICE.resolve() == Path('/dev/sdb')
    assert os.stat('/var/lib/postgresql/12/main').st_dev == os.stat('/srv/odoo-data').st_dev
    assert os.stat('/').st_dev != os.stat('/srv/odoo-data').st_dev
    ROOT.mkdir(mode=0o700, exist_ok=True)
    assert not ROOT.is_symlink() and ROOT.stat().st_uid == 0
    os.chmod(ROOT, 0o700)
    proof_path = ROOT / 'proof.json'
    proof = json.loads(proof_path.read_text()) if proof_path.exists() else {
        'authorized_target_gib': 150, 'database_dml': False, 'service_restart': False,
        'credentials_changed': False, 'backups': {},
        'snapshot_name': 'odoo-data-pre150-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S'),
        'tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}

    def save():
        proof_path.write_text(json.dumps(proof, indent=2), encoding='utf-8')

    def cloud(arguments):
        return json.loads(subprocess.check_output(
            ['sudo', '-H', '-u', actor, gcloud, *arguments, '--project=' + PROJECT,
             '--quiet', '--format=json', '--verbosity=error'], text=True))

    with open('/run/lock/steps-environments.lock', 'a') as lock:
        print('RESIZE_WAITING_SHARED_LEASE', flush=True)
        fcntl.flock(lock, fcntl.LOCK_EX)
        disk = cloud(['compute', 'disks', 'describe', DISK, '--zone=' + ZONE])
        assert disk['name'] == DISK and disk['users'] == [INSTANCE]
        assert disk['type'].endswith('/diskTypes/pd-balanced')
        assert int(disk['sizeGb']) in (100, 150)
        filesystem = subprocess.check_output(['blkid', '-o', 'export', str(DEVICE)], text=True)
        assert 'TYPE=ext4' in filesystem
        proof.setdefault('disk_before', {key: disk[key] for key in ('id', 'name', 'sizeGb', 'selfLink', 'type', 'users')})
        proof.setdefault('filesystem_before', filesystem)
        save()
        run(['sudo', '-u', 'postgres', 'pg_isready', '-q'])

        backup_dir = ROOT / 'backups'
        backup_dir.mkdir(mode=0o700, exist_ok=True)
        for database in ('SyS', 'CERRO_EL_PLOMO'):
            path = backup_dir / (database + '.dump')
            if database not in proof['backups']:
                assert not path.exists(), 'Unrecorded backup must be reviewed, never overwritten'
                with path.open('xb') as stream:
                    run(['sudo', '-u', 'postgres', 'env', 'PGOPTIONS=-c default_transaction_read_only=on',
                         'pg_dump', '-Fc', database], stdout=stream)
                os.chmod(path, 0o600)
                run(['pg_restore', '--no-owner', '--no-acl', '--file=/dev/null', str(path)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                proof['backups'][database] = {'path': str(path), 'bytes': path.stat().st_size,
                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'fully_decoded': True}
                save()
            else:
                assert hashlib.sha256(path.read_bytes()).hexdigest() == proof['backups'][database]['sha256']
            print('RESIZE_BACKUP_VERIFIED ' + database, flush=True)

        if 'snapshot' not in proof:
            assert int(disk['sizeGb']) == 100, 'No pre-resize snapshot recorded; review existing operation'
            name = proof['snapshot_name']
            created = cloud(['compute', 'snapshots', 'create', name, '--source-disk=' + DISK,
                             '--source-disk-zone=' + ZONE,
                             '--description=User-approved backup before Community validation capacity resize'])
            snapshot = cloud(['compute', 'snapshots', 'describe', name])
            assert snapshot['status'] == 'READY' and snapshot['sourceDisk'] == disk['selfLink']
            assert int(snapshot['diskSizeGb']) == 100
            proof['snapshot'] = {key: snapshot[key] for key in ('name', 'status', 'sourceDisk', 'diskSizeGb', 'creationTimestamp')}
            save()
            print('RESIZE_SNAPSHOT_READY', flush=True)

        if int(disk['sizeGb']) == 100:
            cloud(['compute', 'disks', 'resize', DISK, '--zone=' + ZONE, '--size=150GB'])
        current = cloud(['compute', 'disks', 'describe', DISK, '--zone=' + ZONE])
        assert current['id'] == disk['id'] and int(current['sizeGb']) == 150 and current['users'] == [INSTANCE]
        proof['cloud_size_gib'] = 150
        save()
        print('RESIZE_CLOUD_150_GIB', flush=True)

        target_bytes = 150 * 1024 ** 3
        size = int(subprocess.check_output(['blockdev', '--getsize64', str(DEVICE)], text=True))
        if size != target_bytes:
            rescan = Path('/sys/class/block/sdb/device/rescan')
            assert rescan.is_file()
            rescan.write_text('1\n')
            for attempt in range(30):
                size = int(subprocess.check_output(['blockdev', '--getsize64', str(DEVICE)], text=True))
                if size == target_bytes:
                    break
                time.sleep(1)
        assert size == target_bytes
        run(['resize2fs', str(DEVICE)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stat = os.statvfs('/var/lib/postgresql/12/main')
        proof['filesystem_bytes_after'] = stat.f_blocks * stat.f_frsize
        proof['postgres_available_bytes_after'] = stat.f_bavail * stat.f_frsize
        assert proof['filesystem_bytes_after'] > 140 * 1024 ** 3
        assert proof['postgres_available_bytes_after'] >= 5 * 1024 ** 3
        run(['sudo', '-u', 'postgres', 'pg_isready', '-q'])
        proof['postgres_ready_after'] = True
        proof['completed'] = True
        save()
        print(json.dumps({'completed': True, 'cloud_size_gib': 150,
                          'postgres_available_bytes_after': proof['postgres_available_bytes_after'],
                          'snapshot': proof['snapshot']['name'], 'database_dml': False}), flush=True)


if __name__ == '__main__':
    main()
