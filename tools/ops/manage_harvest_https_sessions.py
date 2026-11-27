"""Prepare/remove temporary native sessions for read-only HTTPS acceptance."""
import argparse
import configparser
import json
from pathlib import Path
import subprocess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('prepare', 'cleanup'))
    p.add_argument('base', type=Path)
    a = p.parse_args()
    assert a.base.resolve() == a.base and a.base.parent == Path('/opt/steps-validation')
    tools = Path(__file__).resolve().parent
    registry = json.loads((tools / 'environments.json').read_text())['environments']
    frontend = json.loads((a.base / 'web/release.json').read_text())
    release = json.loads((a.base / 'backend-release.json').read_text())
    assert frontend['version'] == '0.0.12'
    header = (tools / 'native_business_profile.py').read_text()
    source = (tools / 'harvest_cache_browser_session.py').read_text().replace(
        'from native_business_profile import scoped_business_environment\n', '')
    output = a.base / 'https-sessions'
    output.mkdir(mode=0o700, exist_ok=True)
    for name in ('development', 'qa-cerro', 'cerro'):
        target = registry[name]
        proof = Path('/tmp/harvest-cache-browser-t244245-' + name + '.json')
        cleanup = a.action == 'cleanup'
        if cleanup and not proof.exists():
            continue
        if not cleanup:
            stage = a.base.parent / ('management_' + name + '_t244245_' + release['commit'][:8])
            deployed = json.loads((stage / 'harvest-web-deployed.json').read_text())
            assert deployed['web_commit'] == frontend['commit'] and deployed['served'] == frontend['files']
        config = configparser.ConfigParser(interpolation=None)
        config.read(target['config'])
        assert config['options']['db_name'] == target['database']
        user = subprocess.check_output(['systemctl', 'show', '--value', '--property=User', target['service']], text=True).strip()
        assert user in ('odoo', 'cerro_odoo18', 'cerroqa_odoo18')
        code = header + '\nPROOF_PATH=' + repr(str(proof)) + '\nCLEANUP=' + repr(cleanup) + '\n' + source
        result = subprocess.run(['sudo', '-u', user, '/usr/bin/python3.10', '/opt/odoo18/odoo-bin',
            'shell', '-c', target['config'], '-d', target['database'], '--db-filter=^' + target['database'] + '$',
            '--no-http', '--workers=0', '--max-cron-threads=0', '--log-level=critical'],
            input=code, text=True, capture_output=True)
        (a.base / ('https-session-' + name + '-' + a.action + '.log')).write_text(result.stdout + result.stderr)
        marker = 'HARVEST_CACHE_SESSION_REMOVED' if cleanup else 'HARVEST_CACHE_SESSION_READY'
        assert result.returncode == 0 and marker in result.stdout, 'Inspect the private session log: ' + name
        if not cleanup:
            destination = output / (name + '.json')
            destination.write_bytes(proof.read_bytes())
            destination.chmod(0o600)
        print('HARVEST_HTTPS_SESSION_' + a.action.upper() + '_OK ' + name, flush=True)


if __name__ == '__main__':
    main()
