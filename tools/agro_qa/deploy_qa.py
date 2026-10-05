"""Deploy only Development or Demo using a private addon overlay and a DB backup.

Run as root on odoo-new after the same archive passed clone tests. Production
shares Development's old addon root, so that root must never be overwritten.
"""
import argparse
import configparser
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import tarfile
import urllib.request

TARGETS = {
    'development': ('LAB_TAREAS', '/etc/dev_odoo18.conf', 'odoo18-dev.service', 8075),
    'demo': ('STEPS_DEMO', '/etc/demo_odoo18.conf', 'odoo18-demo.service', 8080),
}
MODULES = ('step_export', 'step_producers', 'step_inventory_packing', 'step_producer_fruit_flow', 'step_packing_operations')


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('environment', choices=TARGETS)
    parser.add_argument('archive', type=Path)
    parser.add_argument('sha256')
    parser.add_argument('commit')
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0 or not re.fullmatch('[0-9a-f]{40}', args.commit):
        raise SystemExit('Run as root with the exact Git commit')
    if hashlib.sha256(args.archive.read_bytes()).hexdigest() != args.sha256:
        raise SystemExit('Archive checksum mismatch')
    database, config_path, service, port = TARGETS[args.environment]
    config_path = Path(config_path)
    config = configparser.ConfigParser(interpolation=None)
    config.read(config_path)
    options = config['options']
    if options.get('db_name') not in ('', None, database) or int(options.get('http_port', '0')) != port:
        print(json.dumps({key: options.get(key) for key in ('db_name', 'dbfilter', 'http_port', 'xmlrpc_port')}), flush=True)
        raise SystemExit('Target configuration does not match the QA whitelist')
    service_user = subprocess.check_output(['systemctl', 'show', '--value', '--property=User', service], text=True).strip()
    if not service_user or service_user == 'root':
        raise SystemExit('A dedicated unprivileged Odoo service user is required')
    identity = pwd.getpwnam(service_user)
    addons = options['addons_path'].split(',')
    print(json.dumps({'environment': args.environment, 'database': database, 'service': service, 'user': service_user,
                      'port': port, 'commit': args.commit, 'uses_shared_base': args.environment == 'development'}), flush=True)
    if args.preflight:
        return
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    root = Path('/opt/steps-agro-qa/releases') / args.environment / args.commit
    backup = Path('/opt/backups') / ('agro-qa-' + args.environment + '-' + stamp)
    if root.exists():
        raise SystemExit('Release already exists; use a new reviewed commit')
    root.mkdir(parents=True, mode=0o755)
    with tarfile.open(args.archive, 'r:gz') as archive:
        for member in archive.getmembers():
            path = Path(member.name)
            if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] not in MODULES or not member.isfile():
                raise SystemExit('Unexpected release archive entry')
        archive.extractall(root)
    for path in [root, *root.rglob('*')]:
        os.chown(path, identity.pw_uid, identity.pw_gid)
    backup.mkdir(mode=0o700)
    shutil.copy2(config_path, backup / 'odoo.conf')
    (backup / 'release.json').write_text(json.dumps({'database': database, 'service': service, 'commit': args.commit, 'sha256': args.sha256, 'overlay': str(root)}))
    run('systemctl', 'stop', service)
    try:
        with (backup / 'database.dump').open('wb') as dump:
            run('sudo', '-u', 'postgres', 'pg_dump', '-Fc', database, stdout=dump)
        os.chmod(backup / 'database.dump', 0o600)
        # Preserve every unrelated addon path, including homepage and assistant code.
        kept = [path.strip() for path in addons if not path.strip().startswith('/opt/steps-agro-qa/releases/' + args.environment + '/')]
        new_addons = ','.join([str(root), *kept])
        original = config_path.read_text()
        changed, count = re.subn(r'(?m)^\s*addons_path\s*=.*$', 'addons_path = ' + new_addons, original)
        if count != 1:
            raise RuntimeError('Expected exactly one addon path setting')
        # A shared/multi-DB development service must never load QA code into production.
        for key, value in (('db_name', database), ('dbfilter', '^' + database + '$')):
            changed, count = re.subn(r'(?m)^\s*' + key + r'\s*=.*$', key + ' = ' + value, changed)
            if count == 0:
                changed += '\n' + key + ' = ' + value + '\n'
        config_path.write_text(changed)
        log = root / 'upgrade.log'
        log.touch(mode=0o600)
        os.chown(log, identity.pw_uid, identity.pw_gid)
        run('sudo', '-u', service_user, '/usr/bin/python3.10', '/opt/odoo18/odoo-bin',
            '-c', str(config_path), '-d', database, '--workers=0', '--max-cron-threads=0', '--no-http',
            '--without-demo=all', '-i', ','.join(MODULES), '-u', ','.join(MODULES), '--stop-after-init', '--logfile=' + str(log))
        shutil.copy2(log, backup / 'upgrade.log')
        run('systemctl', 'start', service)
        run('systemctl', 'is-active', '--quiet', service)
        # A 2xx local login response proves the upgraded database can serve HTTP.
        import time
        for attempt in range(30):
            try:
                with urllib.request.urlopen('http://127.0.0.1:%s/web/login?db=%s' % (port, database), timeout=10) as response:
                    if response.status != 200:
                        raise RuntimeError('Unexpected login status')
                break
            except Exception:
                if attempt == 29:
                    raise
                time.sleep(2)
        print('AGRO_QA_DEPLOY_OK ' + json.dumps({'commit': args.commit, 'environment': args.environment, 'backup': str(backup), 'overlay': str(root)}), flush=True)
    except Exception:
        # Keep the recovery evidence and the upgraded DB. Do not silently discard QA data.
        shutil.copy2(backup / 'odoo.conf', config_path)
        run('systemctl', 'start', service)
        print('AGRO_QA_DEPLOY_FAILED backup=' + str(backup), flush=True)
        raise


if __name__ == '__main__':
    main()
