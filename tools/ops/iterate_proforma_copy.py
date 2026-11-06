"""Run diagnostic iterations in an existing private copy; never certify it.

Final publication still requires fresh manage_management QA for the exact package.
"""
import argparse
import configparser
import fcntl
import json
from pathlib import Path
import re
import socket
import subprocess

import manage_management


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('environment', choices=('development', 'cerro', 'qa-cerro'))
    parser.add_argument('run_id')
    parser.add_argument('release', type=Path)
    parser.add_argument('--probe', action='store_true')
    parser.add_argument('--probe-only', action='store_true',
                        help='Reuse successful diagnostic tests only when every addon file is identical')
    args = parser.parse_args()
    assert re.fullmatch('[a-z0-9_]{1,24}', args.run_id)
    database = 'MANAGEMENT_QA_' + args.environment.upper() + '_' + args.run_id
    registry = json.loads((Path(__file__).parent / 'environments.json').read_text())
    target = registry['environments'][args.environment]
    stage = Path('/opt/steps-validation') / ('management_' + args.environment + '_' + args.run_id)
    assert (stage / 'baseline.json').is_file() and not (stage / 'qa_passed.json').exists()
    config = configparser.ConfigParser(interpolation=None)
    config.read(target['config'])
    options = config['options']
    assert options['db_name'] == target['database'] and database != options['db_name']
    source = stage / ('iteration_' + str(len(list(stage.glob('iteration_*')))))
    source.mkdir()
    manage_management.MODULES = ('step_packing_fruit_proforma',)
    proof = manage_management.extract(args.release, source)
    assert set(proof['versions']) == {'step_packing_fruit_proforma'}
    log = source / 'tests.log'
    user = subprocess.check_output(['systemctl', 'show', '--value', '--property=User', target['service']], text=True).strip()
    subprocess.run(['chown', '-R', user, str(source)], check=True)
    with open('/run/lock/steps-environments.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        command = ['sudo', '-u', user, '/usr/bin/python3.10', '/opt/odoo18/odoo-bin',
            '-c', target['config'], '-d', database, '--db-filter=^' + database + '$',
            '--addons-path=' + str(source) + ',' + options['addons_path'],
            '--data-dir=' + str(stage / 'data'), '--no-http', '--workers=0',
            '--http-interface=127.0.0.1', '--http-port=' + str(port), '--gevent-port=0',
            '--max-cron-threads=0', '--without-demo=all', '-u', 'step_packing_fruit_proforma',
            '--test-enable', '--test-tags=/step_packing_fruit_proforma',
            '--stop-after-init', '--logfile=' + str(log)]
        if args.probe_only:
            assert args.probe
            prior = [path for path in stage.glob('iteration_*')
                if (path / 'release.json').is_file() and (path / 'tests.log').is_file()
                and json.loads((path / 'release.json').read_text())['files'] == proof['files']
                and re.search(r'0 failed, 0 error\(s\) of [1-9][0-9]* tests', (path / 'tests.log').read_text())]
            assert prior, 'Run the tests for these exact addon files before probing'
            log = prior[-1] / 'tests.log'
            result = subprocess.CompletedProcess(command, 0, '', '')
        else:
            result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0 and args.probe:
            manage_management.TICKET_REVISION = 'packing-fruit-proforma'
            manage_management.SETTINGS = True
            base = ['sudo', '-u', user, '/usr/bin/python3.10', '/opt/odoo18/odoo-bin']
            switches = ['-c', target['config'], '--no-http', '--http-interface=127.0.0.1',
                '--http-port=0', '--gevent-port=0', '--workers=0', '--max-cron-threads=0', '--without-demo=all']
            manage_management.verify(base, switches, database, source, options,
                proof, stage, set(proof['versions']))
    text = log.read_text(errors='replace')
    print('DIAGNOSTIC_ONLY_NO_CERTIFICATION log=' + str(log), flush=True)
    print('\n'.join(line for line in text.splitlines() if any(
        marker in line for marker in ('tests.result', ' ERROR ', ' FAIL', 'Traceback')))[-6000:])
    if result.returncode:
        print((result.stdout + result.stderr)[-2000:])
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
