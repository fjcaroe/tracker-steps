"""Install and test Productores without Exportaciones in a disposable QA database."""
import configparser
import os
from pathlib import Path
import pwd
import subprocess

DB = 'AGRO_PRODUCERS_STANDALONE_20261005'
ROOT = Path('/opt/steps-agro-qa/producers-standalone')
CONFIG = '/etc/dev_odoo18.conf'


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    assert os.geteuid() == 0
    user = subprocess.check_output(['systemctl', 'show', '--value', '--property=User', 'odoo18-dev.service'], text=True).strip()
    config = configparser.ConfigParser(interpolation=None)
    config.read(CONFIG)
    addons = '/opt/steps-agro-qa/development/phaseb/addons,' + config['options']['addons_path']
    ROOT.mkdir(parents=True, exist_ok=True)
    identity = pwd.getpwnam(user)
    os.chown(ROOT, identity.pw_uid, identity.pw_gid)
    exists = subprocess.check_output(['sudo', '-u', 'postgres', 'psql', '-Atc', "SELECT 1 FROM pg_database WHERE datname='%s'" % DB], text=True).strip()
    if not exists:
        run('sudo', '-u', 'postgres', 'createdb', '-O', 'dev_odoo18', DB)
        run('sudo', '-u', 'postgres', 'psql', '-d', DB, '-v', 'ON_ERROR_STOP=1', '-c', 'CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;')
    common = ['sudo', '-u', user, '/usr/bin/python3.10', '/opt/odoo18/odoo-bin']
    options = ['-c', CONFIG, '-d', DB, '--addons-path=' + addons, '--data-dir=' + str(ROOT), '--no-http',
        '--http-interface=127.0.0.1', '--http-port=0', '--workers=0', '--max-cron-threads=0', '--without-demo=all']
    log = ROOT / 'standalone.log'
    run(*(common + options + ['-i', 'step_producers', '-u', 'step_producers', '--test-enable',
        '--test-tags', '/step_producers:TestProducerEstimate,/step_producers:TestIndependentProducerCore,/step_producers:TestProducerApp', '--stop-after-init', '--logfile=' + str(log)]))
    code = '''
assert env['ir.module.module'].search([('name','=','step_export')]).state == 'uninstalled'
assert 'step.export.receiver.settlement' not in env.registry.models
assert env['ir.module.module'].search([('name','=','step_producers')]).state == 'installed'
assert env['step.export.producer.settlement'].get_view(view_id=env.ref('step_producers.view_export_producer_settlement_form').id,view_type='form')['arch']
print('PRODUCERS_STANDALONE_OK database=' + env.cr.dbname)
env.cr.rollback()
'''
    result = run(*(common + ['shell'] + options + ['--log-level=error']), input=code, text=True, capture_output=True)
    assert 'PRODUCERS_STANDALONE_OK' in result.stdout, result.stderr[-3000:]
    print(result.stdout.strip())
    print('LOG=' + str(log))


if __name__ == '__main__':
    main()
