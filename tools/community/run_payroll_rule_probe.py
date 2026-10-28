"""Run rolled-back rule observations in the accepted private F rehearsal pair."""
import argparse
import configparser
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import subprocess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    a = p.parse_args()
    assert os.geteuid() == 0
    root = a.root.resolve()
    assert re.fullmatch('/opt/steps-validation/community-payroll-rule-collisions-20261028[A-Z]', str(root))
    baseline = Path('/opt/steps-validation/community-payroll-sys-reference-20261028F')
    probe = Path(__file__).with_name('probe_payroll_rule_collisions.py')
    root.mkdir(mode=0o755, exist_ok=True)
    os.chmod(root, 0o755)
    (root/'probe.py').write_bytes(probe.read_bytes())
    os.chmod(root/'probe.py', 0o644)
    with open('/run/lock/steps-environments.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for mode in ('community', 'cerro-reference'):
            pure = mode == 'community'
            user = 'odoo' if pure else 'cerro_odoo18'
            stage = baseline/mode
            accepted = json.loads((stage/'passed.json').read_text())
            assert accepted['profile'] == 'book-history'
            assert accepted['database'] == ('COMMUNITY_PAYROLL_API_' if pure else 'MANAGEMENT_QA_CERRO_PAYROLL_API_')+'SYS_REFERENCE_20261028F'
            target = root/mode
            target.mkdir(mode=0o700, exist_ok=True)
            identity = pwd.getpwnam(user)
            os.chown(target, identity.pw_uid, identity.pw_gid)
            assert not (target/'observations.json').exists(), 'Do not overwrite accepted observations'
            conf = '/etc/dev_odoo18.conf' if pure else '/etc/odoo18-cerroelplomo.conf'
            config = configparser.ConfigParser(interpolation=None)
            assert config.read(conf)
            runtime = Path('/opt/steps-validation/community-foundation-final-20261027/community-runtime')
            paths = str(stage/'addons')+','+(str(runtime/'addons') if pure else config['options']['addons_path'])
            entry = runtime/'odoo-bin' if pure else baseline/'addons/tools/ops/run_agriculture_upgrade.py'
            command = ['sudo', '-u', user, '/usr/bin/python3.10', str(entry), 'shell', '-c', conf,
                       '-d', accepted['database'], '--addons-path='+paths, '--data-dir='+str(stage/'data'),
                       '--no-http', '--load=base,web', '--workers=0', '--max-cron-threads=0',
                       '--logfile='+str(target/'probe.log')]
            expression = 'import runpy;runpy.run_path('+repr(str(root/'probe.py'))+')["exercise"](env,'+repr(str(target/'observations.json'))+')'
            status = subprocess.run(command, input=expression, text=True, capture_output=True)
            (target/'bootstrap.log').write_text(status.stdout+status.stderr)
            assert status.returncode == 0 and (target/'observations.json').is_file(), str(target/'bootstrap.log')
            proof = json.loads((target/'observations.json').read_text())
            assert proof['normal_actor'] and proof['fixtures_rolled_back'] and proof['synthetic_only']
            assert not proof['financial_certified'] and not proof['writes_to_source']
            proof['probe_sha256'] = hashlib.sha256(probe.read_bytes()).hexdigest()
            proof['runner_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            proof['baseline_source_files_sha256'] = accepted['source_files_sha256']
            (target/'observations.json').write_text(json.dumps(proof, indent=2))
            print(json.dumps(proof), flush=True)


if __name__ == '__main__':
    main()
