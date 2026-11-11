"""Run the authorized Cerro receipt correction using the installed, tested addon."""
import argparse
import configparser
import fcntl
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess

from manage_management import query, tree_hash


HERE = Path(__file__).resolve().parent
MODULE = 'step_packing_reception_revision'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('rehearse', 'apply', 'verify'))
    parser.add_argument('plan', type=Path)
    parser.add_argument('proof_dir', type=Path)
    parser.add_argument('--clone')
    args = parser.parse_args()
    assert args.plan.is_file()
    if args.phase == 'rehearse':
        assert args.clone and args.clone.startswith('MANAGEMENT_QA_CERRO_')
    else:
        assert not args.clone
    plan = json.loads(args.plan.read_text())
    registry = json.loads((HERE / 'environments.json').read_text())
    target = registry['environments']['cerro']
    assert target['database'] == 'CERRO_EL_PLOMO'
    conf = Path(target['config'])
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(conf)
    opts = cfg['options']
    assert opts['db_name'] == target['database']
    source = next(Path(root.strip()) / MODULE for root in opts['addons_path'].split(',')
                  if (Path(root.strip()) / MODULE / '__manifest__.py').is_file())
    release = json.loads((source.parent / 'release.json').read_text())
    assert release['commit'] == plan['release_commit']
    assert release['versions'][MODULE] == query(target['database'],
        "SELECT latest_version FROM ir_module_module WHERE name='%s' AND state='installed'" % MODULE)
    expected = {
        'plan_sha256': digest(args.plan), 'helper_sha256': digest(HERE / 'receipt_product_case.py'),
        'runner_sha256': digest(Path(__file__)), 'addon_sha256': tree_hash(source),
        'config_sha256': digest(conf),
    }
    args.proof_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    with open('/run/lock/steps-environments.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        assert digest(conf) == expected['config_sha256']
        assert not query(target['database'],
            "SELECT name FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove')")
        assert tree_hash(source) == expected['addon_sha256']
        if args.phase == 'apply':
            certified = json.loads((args.proof_dir / 'rehearsed.json').read_text())
            assert certified['inputs'] == expected
            assert certified['database'].startswith('MANAGEMENT_QA_CERRO_')
        worker = subprocess.check_output(
            ['systemctl', 'show', '--value', '--property=User', target['service']], text=True).strip()
        database = args.clone or target['database']
        script = ('import json,sys\nsys.path.insert(0,%r)\nCASE=json.loads(%r)\nPHASE=%r\n' %
                  (str(HERE), args.plan.read_text(), args.phase))
        script += (HERE / 'receipt_product_case.py').read_text()
        command = ['sudo', '-u', worker, '/usr/bin/python3.10', '/opt/odoo18/odoo-bin',
                   'shell', '-c', str(conf), '-d', database, '--no-http', '--workers=0',
                   '--max-cron-threads=0', '--log-level=error', '--db-filter=^' + database + '$']
        backup = None
        stopped = False
        try:
            if args.phase == 'apply':
                stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
                backup = Path('/opt/steps_backups') / ('receipt_product_cerro_' + stamp)
                backup.mkdir(mode=0o700)
                shutil.copy2(conf, backup / 'odoo.conf')
                subprocess.run(['systemctl', 'stop', target['service']], check=True)
                stopped = True
                with (backup / 'database.dump').open('wb') as stream:
                    subprocess.run(['sudo', '-u', 'postgres', 'pg_dump', '-Fc', database],
                                   stdout=stream, check=True)
                filestore = Path(opts['data_dir']) / 'filestore' / database
                if filestore.exists():
                    subprocess.run(['rsync', '-a', str(filestore) + '/', str(backup / 'filestore') + '/'],
                                   check=True)
            result = subprocess.run(command, input=script, text=True, capture_output=True)
            (args.proof_dir / (args.phase + '.log')).write_text(result.stdout + result.stderr)
            marker = next((line for line in result.stdout.splitlines() if line.startswith('T196_CASE_OK ')), None)
            assert result.returncode == 0 and marker, result.stderr[-3000:]
            outcome = json.loads(marker.removeprefix('T196_CASE_OK '))
            record = {'inputs': expected, 'database': database, 'result': outcome,
                      'backup': str(backup) if backup else None}
            filename = 'rehearsed.json' if args.phase == 'rehearse' else args.phase + '.json'
            (args.proof_dir / filename).write_text(json.dumps(record, indent=2))
            print('RECEIPT_PRODUCT_OPERATION_OK ' + json.dumps(record), flush=True)
        finally:
            if stopped:
                subprocess.run(['systemctl', 'start', target['service']], check=True)
        if args.phase != 'rehearse':
            subprocess.run(['systemctl', 'is-active', '--quiet', target['service']], check=True)


if __name__ == '__main__':
    main()
