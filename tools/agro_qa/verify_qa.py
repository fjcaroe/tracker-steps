"""Check deployed QA code, versions and compiled forms without changing business data."""
import argparse
import configparser
import json
from pathlib import Path
import re
import subprocess
import urllib.request

TARGETS = {
    'development': ('LAB_TAREAS', '/etc/dev_odoo18.conf', 'odoo18-dev.service', 'https://desarrollo.stepsapp.cl'),
    'demo': ('STEPS_DEMO', '/etc/demo_odoo18.conf', 'odoo18-demo.service', 'https://demo.stepsapp.cl'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('environment', choices=TARGETS)
    parser.add_argument('commit')
    args = parser.parse_args()
    if not re.fullmatch('[0-9a-f]{40}', args.commit):
        raise SystemExit('An exact commit is required')
    database, config_path, service, url = TARGETS[args.environment]
    config = configparser.ConfigParser(interpolation=None)
    config.read(config_path)
    root = '/opt/steps-agro-qa/releases/%s/%s' % (args.environment, args.commit)
    assert config['options']['addons_path'].split(',')[0] == root
    assert config['options']['db_name'] == database
    assert config['options']['dbfilter'] == '^' + database + '$'
    user = subprocess.check_output(['systemctl', 'show', '--value', '--property=User', service], text=True).strip()
    subprocess.run(['systemctl', 'is-active', '--quiet', service], check=True)
    code = '''
import importlib, json
expected = {'step_export': '18.0.2.7.0', 'step_producers': '18.0.1.6.0',
    'step_inventory_packing': '18.0.1.1.0', 'step_packing_operations': '18.0.2.6.0',
    'step_producer_fruit_flow': '18.0.1.2.0'}
try:
    versions = {}
    for name, version in expected.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed', (name, module.state)
        assert module.latest_version == version, (name, module.latest_version)
        source = importlib.import_module('odoo.addons.' + name).__file__
        assert source.startswith(ROOT + '/'), (name, source)
        versions[name] = module.latest_version
    forms = (
        ('step.packing.production', 'step_packing_operations.view_packing_production_form'),
        ('step.packing.order', 'step_packing_operations.view_packing_order_form'),
        ('step.packing.inspection', 'step_packing_operations.view_packing_inspection_form'),
        ('step.packing.instruction', 'step_packing_operations.view_packing_instruction_form'),
        ('step.packing.monthly.fruit.bill', 'step_packing_operations.view_monthly_fruit_bill'),
        ('step.producer.season.statement', 'step_producers.view_season_statement_form'),
        ('step.producer.season.statement.wizard', 'step_producers.view_season_statement_wizard'),
    )
    for model, xmlid in forms:
        assert env[model].get_view(view_id=env.ref(xmlid).id, view_type='form')['arch']
    print('AGRO_QA_REGISTRY_OK ' + json.dumps({'database': env.cr.dbname, 'versions': versions, 'compiled_forms': len(forms)}))
finally:
    env.cr.rollback()
'''
    code = 'ROOT = ' + repr(root) + '\n' + code
    result = subprocess.run(['sudo', '-u', user, '/usr/bin/python3.10', '/opt/odoo18/odoo-bin',
                    'shell', '-c', config_path, '-d', database, '--no-http',
                    '--workers=0', '--max-cron-threads=0', '--log-level=error'],
                   input=code, text=True, capture_output=True)
    if result.returncode:
        print('\n'.join((result.stdout + result.stderr).splitlines()[-40:]))
        raise SystemExit(result.returncode)
    registry_result = [line for line in result.stdout.splitlines() if line.startswith('AGRO_QA_REGISTRY_OK ')]
    assert len(registry_result) == 1, 'Registry verification did not complete'
    print(registry_result[0], flush=True)
    with urllib.request.urlopen(url + '/web/login?db=' + database, timeout=30) as response:
        assert response.status == 200
        assert b'password' in response.read()
    print('AGRO_QA_VERIFY_OK ' + json.dumps({'environment': args.environment, 'commit': args.commit, 'url': url, 'http': 200}))


if __name__ == '__main__':
    main()
