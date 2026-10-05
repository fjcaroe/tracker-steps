"""Deploy the reference chatbot to SyS, then enable IA with the existing demo key."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import time
from urllib.request import urlopen

from lxml import html

from inspect_sys import process_environment, query


def fingerprint(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob('*') if path.is_file()
            and '__pycache__' not in path.parts and path.suffix != '.pyc'}


def public_home():
    with urlopen('https://sys.stepsapp.cl/', timeout=60) as response:
        return response.read()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('sha256')
    parser.add_argument('commit')
    args = parser.parse_args()
    assert os.geteuid() == 0, 'Run as root'
    assert re.fullmatch(r'[a-f0-9]{40}', args.commit), 'Published commit required'
    assert re.fullmatch(r'[a-f0-9]{64}', args.sha256)
    assert hashlib.sha256(args.archive.read_bytes()).hexdigest() == args.sha256
    tools = Path(__file__).resolve().parent
    source_root = Path('/opt/demosys_odoo18/odoo_agriculture')
    modules = ('step_support_assistant', 'step_support_assistant_knowledge')
    before_files = {name: fingerprint(source_root / name) for name in modules}
    with tarfile.open(args.archive) as release:
        for item in release.getmembers():
            if not item.isfile():
                continue
            relative = Path(item.name)
            assert not relative.is_absolute() and '..' not in relative.parts
            assert relative.parts[0] in modules
            actual = (source_root / relative).read_bytes()
            expected = release.extractfile(item).read()
            if relative.suffix in {'.py', '.xml', '.csv', '.js', '.scss', '.svg', '.md'}:
                actual, expected = actual.replace(b'\r\n', b'\n'), expected.replace(b'\r\n', b'\n')
            assert actual == expected, 'Release differs from demo-sys: ' + item.name
    credential_file = Path('/etc/steps/assistant-demo-sys.env')
    credential_before = credential_file.read_bytes()
    source_settings_sql = "SELECT key,value FROM ir_config_parameter WHERE key IN " \
        "('step_support_assistant.enabled','step_support_assistant.model'," \
        "'step_support_assistant.hourly_limit','step_support_assistant.daily_limit') ORDER BY key"
    source_settings_before = query('STEPS_DEMO_SYS', source_settings_sql)
    source_pid = subprocess.check_output(['systemctl', 'show', 'odoo18-demo-sys.service',
                                         '-p', 'MainPID', '--value'], text=True).strip()
    homepage_sql = "SELECT id,key,website_id,md5(arch_db::text) FROM ir_ui_view WHERE " \
        "key='website.homepage' OR key LIKE 'step_demo_homepage.%' ORDER BY id"
    homepage_before = query('SyS', homepage_sql)
    home_bytes = public_home()
    backup = Path('/opt/backups') / ('steps-assistant-sys-activation-' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()))
    backup.mkdir(mode=0o700)
    (backup / 'sys-home.before.html').write_bytes(home_bytes)
    (backup / 'assistant-settings.before.txt').write_text(query('SyS', source_settings_sql))
    (backup / 'release.json').write_text(json.dumps({'commit': args.commit, 'sha256': args.sha256}))
    override = Path('/etc/systemd/system/odoo18-sys.service.d/steps-assistant.conf')
    if override.exists():
        assert not override.is_symlink()
        (backup / 'steps-assistant.conf.before').write_bytes(override.read_bytes())
    else:
        (backup / 'steps-assistant.conf.was_absent').touch()
    subprocess.run(['/usr/bin/python3', str(tools / 'share_sys_credentials.py')], check=True)
    subprocess.run(['bash', str(tools / 'deploy_environment.sh'), 'sys-produccion',
                    str(args.archive), args.sha256], check=True)
    subprocess.run(['/usr/bin/python3', str(tools / 'verify_release.py'),
                    str(args.archive), '/opt/luis_odoo18/odoo_agriculture'], check=True)
    subprocess.run(['/usr/bin/python3', str(tools / 'enable_sys.py')], check=True)
    # Reload only SyS so every worker starts with the committed IA parameters.
    subprocess.run(['systemctl', 'restart', 'odoo18-sys.service'], check=True)
    subprocess.run(['curl', '--fail', '--silent', '--show-error', '--retry', '20',
                    '--retry-connrefused', '--retry-delay', '2',
                    'https://sys.stepsapp.cl/web/login', '--output', '/dev/null'], check=True)
    assert process_environment('odoo18-sys.service').get('OPENAI_API_KEY', '').strip() == \
        process_environment('odoo18-demo-sys.service').get('OPENAI_API_KEY', '').strip()
    assert credential_file.read_bytes() == credential_before, 'Reference credential file changed'
    assert source_settings_before == query('STEPS_DEMO_SYS', source_settings_sql)
    assert source_pid == subprocess.check_output(['systemctl', 'show', 'odoo18-demo-sys.service',
                                                 '-p', 'MainPID', '--value'], text=True).strip()
    assert before_files == {name: fingerprint(source_root / name) for name in modules}
    assert homepage_before == query('SyS', homepage_sql), 'SyS home templates changed'
    after = public_home()
    for page in (home_bytes, after):
        assert html.fromstring(page).xpath('//*[@data-commercial-version="2026.10"]')
    before_text = ' '.join(html.fromstring(home_bytes).xpath('//*[@class="oe_structure step-demo-home"]')[0].text_content().split())
    after_text = ' '.join(html.fromstring(after).xpath('//*[@class="oe_structure step-demo-home"]')[0].text_content().split())
    assert before_text == after_text, 'SyS public home content changed'
    (backup / 'sys-home.after.html').write_bytes(after)
    (backup / 'verification.txt').write_text('IA checks passed; same key; demo-sys unchanged; SyS home unchanged\n')
    print('SYS_PRODUCTION_CHATBOT_READY ' + json.dumps({
        'url': 'https://sys.stepsapp.cl/odoo', 'database': 'SyS', 'commit': args.commit,
        'activation_backup': str(backup), 'same_key': True,
        'demo_sys': 'unchanged', 'sys_home': 'unchanged',
    }))


if __name__ == '__main__':
    main()
