"""Read-only SyS inventory. Credentials are inspected in memory and never printed."""
import configparser
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile


ENVIRONMENTS = (
    ('demo-sys', 'STEPS_DEMO_SYS', '/etc/odoo18-demo-sys.conf', 'odoo18-demo-sys.service',
     '/opt/demosys_odoo18/odoo_agriculture'),
    ('sys', 'SyS', '/etc/odoo18-sys.conf', 'odoo18-sys.service',
     '/opt/luis_odoo18/odoo_agriculture'),
)


def query(database, sql):
    return subprocess.check_output(['sudo', '-n', '-u', 'postgres', 'psql', '-d',
                                    database, '-Atc', sql], text=True).strip()


def process_environment(service):
    pid = subprocess.check_output(['systemctl', 'show', service, '-p', 'MainPID',
                                   '--value'], text=True).strip()
    assert pid.isdigit() and pid != '0', 'Service must be running: ' + service
    return dict(item.split('=', 1) for item in (Path('/proc') / pid / 'environ')
                .read_bytes().decode().split('\0') if '=' in item)


def main():
    source_key = ''
    for label, database, filename, service, addons in ENVIRONMENTS:
        config = configparser.ConfigParser(interpolation=None)
        config.read(filename)
        runtime = process_environment(service)
        key = runtime.get('OPENAI_API_KEY', '').strip()
        if label == 'demo-sys':
            source_key = key
        print(json.dumps({'environment': label, 'database': database,
                          'config': filename, 'port': config['options'].get('http_port'),
                          'addons_path': config['options'].get('addons_path'),
                          'service': service, 'api_key_available': bool(key),
                          'key_format_valid': bool(re.fullmatch(r'sk-[A-Za-z0-9_-]{20,}', key)),
                          'key_has_complete_candidate': bool(re.search(r'sk-[A-Za-z0-9_-]{20,}', key)),
                          'key_has_assignment_wrapper': key.startswith('OPENAI_API_KEY='),
                          'key_has_literal_quote_wrapper': len(key) > 2 and key[0] == key[-1]
                          and key[0] in {'"', "'", '`'},
                          'key_has_whitespace': any(char.isspace() for char in key),
                          'key_has_non_ascii': bool(key and not key.isascii()),
                          'same_key_as_demo': bool(key and key == source_key)}))
        for sql in (
            "SELECT name,state,latest_version FROM ir_module_module WHERE name IN "
            "('step_support_assistant','step_support_assistant_knowledge','knowledge') ORDER BY name;",
            "SELECT key,value FROM ir_config_parameter WHERE key IN "
            "('step_support_assistant.enabled','step_support_assistant.model',"
            "'step_support_assistant.hourly_limit','step_support_assistant.daily_limit') ORDER BY key;",
            "SELECT count(*) FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove');",
        ):
            print(query(database, sql))
        module = Path(addons) / 'step_support_assistant'
        print(json.dumps({'module_directory': str(module), 'exists': module.is_dir()}))
    path = Path('/etc/steps/assistant-demo-sys.env')
    print(json.dumps({'source_env_file': str(path), 'exists': path.exists(),
                      'mode': oct(path.stat().st_mode & 0o777) if path.exists() else None}))
    # Capture only public addon code from the reference, never its data or credentials.
    root = Path(ENVIRONMENTS[0][4])
    output = Path('/tmp/steps-assistant-demo-sys-source.tar.gz')
    allowed = {'.py', '.xml', '.csv', '.js', '.scss', '.svg', '.png', '.md'}
    with tarfile.open(output, 'w:gz') as archive:
        for module in ('step_support_assistant', 'step_support_assistant_knowledge'):
            for item in sorted((root / module).rglob('*')):
                if item.is_file() and item.suffix in allowed and '__pycache__' not in item.parts:
                    archive.add(item, arcname=str(item.relative_to(root)), recursive=False)
    output.chmod(0o644)
    print('PUBLIC_CODE_ARCHIVE=' + str(output))
    print('PUBLIC_CODE_SHA256=' + hashlib.sha256(output.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
