"""Activate SyS with whitelisted demo settings and its existing runtime key."""
import json
import os
from pathlib import Path
import re
import subprocess

from inspect_sys import process_environment, query


def main():
    assert os.geteuid() == 0, 'Run as root'
    reference = process_environment('odoo18-demo-sys.service')
    target = process_environment('odoo18-sys.service')
    key = target.get('OPENAI_API_KEY', '').strip()
    assert key and key == reference.get('OPENAI_API_KEY', '').strip(), 'SyS must load the same existing key'
    result = query('STEPS_DEMO_SYS', "SELECT json_object_agg(key,value) FROM ir_config_parameter "
                   "WHERE key IN ('step_support_assistant.enabled','step_support_assistant.model',"
                   "'step_support_assistant.hourly_limit','step_support_assistant.daily_limit')")
    source = {name.split('.')[-1]: value for name, value in json.loads(result).items()}
    assert source['enabled'] in ('True', 'true', '1'), 'Reference IA must be enabled'
    assert re.fullmatch(r'[a-zA-Z0-9._-]{1,100}', source['model']), 'Invalid model setting'
    assert 1 <= int(source['hourly_limit']) <= 200 and 1 <= int(source['daily_limit']) <= 10000
    script = 'SOURCE_CONFIG = ' + repr(source) + '\n' + (Path(__file__).parent / 'enable_sys_in_odoo.py').read_text()
    runtime = os.environ.copy()
    runtime['OPENAI_API_KEY'] = key
    command = ['sudo', '-n', '--preserve-env=OPENAI_API_KEY', '-u', 'odoo',
               '/opt/odoo18/venv/bin/python', '/opt/odoo18/odoo-bin', 'shell',
               '-c', '/etc/odoo18-sys.conf', '-d', 'SyS', '--no-http',
               '--workers=0', '--max-cron-threads=0',
               '--logfile=/tmp/steps-assistant-sys-activation.log']
    subprocess.run(command, input=script, text=True, env=runtime, check=True)
    print('SYS_RUNTIME_KEY_MATCHES_REFERENCE')


if __name__ == '__main__':
    main()
