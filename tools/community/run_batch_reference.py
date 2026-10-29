"""Observe the actual native batch provider in a private, transactional rehearsal.

No Community provider is installed and no active environment is selected here.
The diagnostic database must already be an isolated native reference.
"""
import argparse
import configparser
import fcntl
import json
import os
from pathlib import Path
import pwd
import re
import socket
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--database', required=True)
    args = parser.parse_args()
    assert os.geteuid() == 0
    assert re.fullmatch(r'MANAGEMENT_QA_CERRO_PAYROLL_API_[A-Za-z0-9_]+', args.database)
    for path in (args.root, args.source, args.reference):
        assert str(path.resolve()).startswith('/opt/steps-validation/')
    assert not args.root.exists()
    args.root.mkdir(mode=0o750)
    config = configparser.ConfigParser(interpolation=None)
    assert config.read('/etc/odoo18-cerroelplomo.conf')
    sys.path.insert(0, str(args.source / 'tools/community'))
    from validate_community_reports import sql
    import validate_agriculture_core as preservation
    preservation.MODULES = (preservation.BASE_MODULES + preservation.PRODUCER_MODULES
        + preservation.OPERATIONS_MODULES + preservation.LABOR_MODULES
        + preservation.HARVEST_MODULES + preservation.HR_MODULES)
    snapshot = preservation.snapshot
    assert sql(args.database, "SELECT count(*) FROM ir_module_module WHERE name='account_batch_payment' AND state='installed'") == '1'
    assert sql(args.database, "SELECT count(*) FROM ir_module_module WHERE name='step_batch_payment_core' AND state='installed'") == '0'
    with open('/run/lock/steps-environments.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        # Reinstalled modules can reactivate cron records in a diagnostic copy.
        # Disable the copy's outbound/background metadata before the baseline.
        sql(args.database, 'UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false;')
        before = snapshot(args.database)
        overlay = args.root / 'addons'
        overlay.mkdir()
        (overlay / 'step_batch_payment_grouping').symlink_to(args.source / 'step_batch_payment_grouping')
        identity = pwd.getpwnam('cerro_odoo18')
        os.chown(args.root, identity.pw_uid, identity.pw_gid)
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        paths = ','.join((str(overlay), str(args.reference / 'cerro-reference/addons'), config['options']['addons_path']))
        command = ['sudo', '-u', 'cerro_odoo18', 'env',
            'COMMUNITY_BATCH_REFERENCE_OUTPUT=' + str(args.root / 'reference.json'),
            '/usr/bin/python3.10', str(args.source / 'tools/ops/run_agriculture_upgrade.py'),
            '-c', '/etc/odoo18-cerroelplomo.conf', '-d', args.database,
            '--db-filter=^' + args.database + '$', '--addons-path=' + paths,
            '--data-dir=' + str(args.reference / 'cerro-reference/data'),
            '--load=base,web', '--workers=0', '--max-cron-threads=0',
            '--http-interface=127.0.0.1', '--http-port=' + str(port), '--gevent-port=0',
            '--without-demo=all', '--stop-after-init', '-i', 'step_batch_payment_grouping',
            '--test-enable', '--test-tags=/step_batch_payment_grouping:BatchGroupingCase.test_native_reference_observes_draft_and_posted_amount_contract',
            '--logfile=' + str(args.root / 'probe.log')]
        with (args.root / 'bootstrap.log').open('w') as stream:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
        log = (args.root / 'probe.log').read_text(errors='replace')
        after = snapshot(args.database)
        # New module/metadata are expected; every original table and sequence
        # retains its rows. The metadata tables themselves are not in snapshot.
        assert all(after[name] == value for name, value in before.items())
        (args.root / 'preservation.json').write_text(json.dumps({'before': before, 'after': after}, indent=2))
        print('\n'.join(line for line in log.splitlines() if ' ERROR ' in line or 'tests.result' in line)[-5000:])
        assert result.returncode == 0 and not re.search(r' (ERROR|CRITICAL) ', log)
        assert '0 failed, 0 error(s) of 1 tests' in log
        assert (args.root / 'reference.json').exists()
        print('NATIVE_BATCH_OBSERVATION_OK')


if __name__ == '__main__':
    main()
