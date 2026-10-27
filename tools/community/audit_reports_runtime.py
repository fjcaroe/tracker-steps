"""Read-only post-start audit of the service, effective overlay and business flow."""
import argparse
import configparser
import json
from pathlib import Path
import subprocess

from manage_community_reports import TARGETS, MODULES, digest, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--environment', choices=TARGETS, required=True)
    parser.add_argument('--release', type=Path, required=True)
    args = parser.parse_args()
    database, conf, service, user, url = TARGETS[args.environment]
    release = args.release.resolve()
    proof = json.loads((release / 'deployed.json').read_text())
    assert proof['url'] == url
    run('systemctl', 'is-active', '--quiet', service)
    identity = run('systemctl', 'show', service, '-p', 'User', '--value', capture_output=True, text=True).stdout.strip()
    assert identity == user
    pid = int(run('systemctl', 'show', service, '-p', 'MainPID', '--value', capture_output=True, text=True).stdout.strip())
    argv = Path('/proc/%s/cmdline' % pid).read_bytes().decode().split('\0')
    assert conf in argv or '--config=' + conf in argv
    config = configparser.ConfigParser(interpolation=None); config.read(conf)
    for index, arg in enumerate(argv):
        for flag, key in (('-d', 'db_name'), ('--database', 'db_name'), ('--data-dir', 'data_dir'), ('--addons-path', 'addons_path')):
            if arg == flag:
                assert argv[index + 1] == config['options'].get(key), 'Conflicting service override: ' + flag
            elif arg.startswith(flag + '='):
                assert arg.split('=', 1)[1] == config['options'].get(key), 'Conflicting service override: ' + flag
    assert config['options']['db_name'] == database
    assert config['options']['addons_path'].split(',')[0].strip() == str(release / 'addons')
    actual = {str(p.relative_to(release / 'addons')): digest(p) for name in MODULES
              for p in (release / 'addons' / name).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}
    assert actual == proof['source_files']
    command = ['sudo', '-u', user, '/usr/bin/python3.10', '/opt/odoo18/odoo-bin', 'shell',
               '-c', conf, '-d', database, '--no-http', '--load=base,web', '--log-level=critical']
    probe = (Path(__file__).parent / 'verify_community_reports.py').read_text()
    result = run(*command, input='MODE=' + repr(args.environment) + '\n' + probe, text=True, capture_output=True)
    (release / 'post-start-verify.log').write_text(result.stdout + result.stderr)
    assert 'COMMUNITY_REPORTS_NATIVE_FLOW_OK' in result.stdout and 'COMMUNITY_TREASURY_REGISTRY_OK' in result.stdout
    (release / 'runtime-passed.json').write_text(json.dumps({'environment': args.environment, 'pid': pid,
        'service_config_verified': True, 'addon_files': len(actual), 'five_business_flows': True}, indent=2))
    print('COMMUNITY_REPORTS_RUNTIME_OK ' + args.environment + ' service_config=True five_flows=True files=' + str(len(actual)))


if __name__ == '__main__': main()
