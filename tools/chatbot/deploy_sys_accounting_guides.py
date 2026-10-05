"""Upgrade only SyS's assistant and set its accounting guide profile safely."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from inspect_sys import process_environment, query

SETTINGS = "SELECT key,value FROM ir_config_parameter WHERE key IN (" \
    "'step_support_assistant.enabled','step_support_assistant.model'," \
    "'step_support_assistant.hourly_limit','step_support_assistant.daily_limit') ORDER BY key"
HOME = "SELECT id,key,website_id,md5(arch_db::text) FROM ir_ui_view " \
    "WHERE key='website.homepage' OR key LIKE 'step_demo_homepage.%' ORDER BY id"
GUIDES = "SELECT d.name,md5(a.content),a.published,a.active,a.company_id " \
    "FROM ir_model_data d JOIN step_assistant_article a ON d.res_id=a.id " \
    "WHERE d.module='step_support_assistant' AND d.model='step.assistant.article' " \
    "AND d.name IN ('help_assistant_scope','help_support_request','help_permissions'," \
    "'help_business_queries','help_colaciones_start','help_colaciones_duplicate'," \
    "'help_colaciones_offline','help_colaciones_tariff') ORDER BY d.name"


def demo_snapshot():
    return {'settings': query('STEPS_DEMO_SYS', SETTINGS),
            'profile': query('STEPS_DEMO_SYS', "SELECT value FROM ir_config_parameter "
                             "WHERE key='step_support_assistant.guide_profile'"),
            'version': query('STEPS_DEMO_SYS', "SELECT latest_version FROM ir_module_module "
                             "WHERE name='step_support_assistant'"),
            'pid': subprocess.check_output(['systemctl', 'show', 'odoo18-demo-sys.service',
                                            '-p', 'MainPID', '--value'], text=True).strip()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('sha256')
    parser.add_argument('commit')
    args = parser.parse_args()
    assert os.geteuid() == 0 and re.fullmatch(r'[0-9a-f]{40}', args.commit)
    assert hashlib.sha256(args.archive.read_bytes()).hexdigest() == args.sha256
    baseline = {'settings': query('SyS', SETTINGS), 'home': query('SyS', HOME),
                'guides': query('SyS', GUIDES), 'demo': demo_snapshot(),
                'profile': query('SyS', "SELECT value FROM ir_config_parameter "
                                 "WHERE key='step_support_assistant.guide_profile'")}
    key = process_environment('odoo18-sys.service').get('OPENAI_API_KEY', '').strip()
    assert key and key == process_environment('odoo18-demo-sys.service').get('OPENAI_API_KEY', '').strip()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = Path('/opt/backups') / ('steps-assistant-sys-accounting-' + stamp)
    backup.mkdir(mode=0o700)
    metadata = backup / 'before.json'
    metadata.write_text(json.dumps(baseline), encoding='utf-8')
    metadata.chmod(0o600)
    root = Path(__file__).parent
    subprocess.run(['bash', str(root / 'deploy_environment.sh'), 'sys-produccion',
                    str(args.archive), args.sha256], check=True)
    subprocess.run(['python3', str(root / 'verify_release.py'), str(args.archive),
                    '/opt/luis_odoo18/odoo_agriculture'], check=True)
    runtime = os.environ.copy()
    runtime['OPENAI_API_KEY'] = key
    subprocess.run(['sudo', '-n', '--preserve-env=OPENAI_API_KEY', '-u', 'odoo',
                    '/opt/odoo18/venv/bin/python', '/opt/odoo18/odoo-bin', 'shell',
                    '-c', '/etc/odoo18-sys.conf', '-d', 'SyS', '--no-http',
                    '--workers=0', '--max-cron-threads=0',
                    '--logfile=/tmp/steps-assistant-sys-accounting-check.log'],
                   input=(root / 'accounting_profile_in_odoo.py').read_text(),
                   text=True, env=runtime, check=True)
    # Each worker must reload the committed profile parameter.
    subprocess.run(['systemctl', 'restart', 'odoo18-sys.service'], check=True)
    subprocess.run(['curl', '--fail', '--silent', '--retry', '20', '--retry-delay', '2',
                    '--retry-connrefused', '--max-time', '15', '--output', '/dev/null',
                    'https://sys.stepsapp.cl/web/login'], check=True)
    assert query('SyS', SETTINGS) == baseline['settings'], 'IA settings must remain unchanged'
    assert query('SyS', HOME) == baseline['home'], 'Home must remain unchanged'
    assert query('SyS', GUIDES) == baseline['guides'], 'Existing approved content must be preserved'
    assert demo_snapshot() == baseline['demo'], 'Demo-SyS must remain unchanged'
    assert process_environment('odoo18-sys.service').get('OPENAI_API_KEY', '').strip() == key
    assert query('SyS', "SELECT value FROM ir_config_parameter "
                 "WHERE key='step_support_assistant.guide_profile'") == 'accounting'
    print('SYS_ACCOUNTING_DEPLOY_OK ' + json.dumps({
        'commit': args.commit, 'sha256': args.sha256, 'metadata_backup': str(backup),
        'same_key': True, 'ia_settings_preserved': True, 'home_preserved': True,
        'previous_guide_content_preserved': True, 'demo_preserved': True,
    }))


if __name__ == '__main__':
    main()
