"""Redirect legacy public ports while retaining Odoo's loopback upstreams.

Run on odoo-new as root. This changes network/URL configuration only, never
addon code or business records. A separate redirect listener uses the VM's
private address (GCP NAT); nginx's HTTPS proxies keep using 127.0.0.1.
"""
import argparse
import configparser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import fcntl
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parent
SITE = Path('/etc/nginx/sites-available/steps-canonical-ports')
ENABLED = Path('/etc/nginx/sites-enabled/steps-canonical-ports')


def run(*command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def query(database, sql):
    return subprocess.check_output(['sudo', '-u', 'postgres', 'psql', '-v', 'ON_ERROR_STOP=1', '-d', database, '-Atc', sql], text=True).strip()


def setting(text, name, value):
    # Odoo config parsers read the last duplicate; ambiguity must be repaired first.
    result, count = re.subn(r'(?m)^\s*' + name + r'\s*=.*$', name + ' = ' + value, text)
    assert count <= 1, 'Duplicate configuration option: ' + name
    return result if count else text.rstrip() + '\n' + name + ' = ' + value + '\n'


def login(target):
    suffix = '/web/login' + ('?db=' + target['database'] if target['database'] else '')
    try:
        with urllib.request.urlopen(target['url'] + suffix, timeout=30) as response:
            assert response.status == 200 and b'password' in response.read(), target['label']
    except urllib.error.HTTPError as error:
        # Admin's legacy multi-DB installation already returns 500 before this
        # change. Keep redirecting its URL, without claiming its apps are healthy.
        if target['label'] != 'Admin Studio' or error.code != 500:
            raise
        print('KNOWN_BASELINE_HTTP_500 environment=admin', flush=True)


def redirect(ip, target):
    uri = '/odoo?menu_id=42&canonical_probe=1'
    for method in ('GET', 'POST'):
        conn = http.client.HTTPConnection(ip, target['port'], timeout=15)
        try:
            conn.request(method, uri, body=b'' if method == 'POST' else None,
                         headers={'Host': 'untrusted.example', 'Connection': 'close'})
            response = conn.getresponse()
            assert response.status == 308, (target['label'], response.status)
            assert response.getheader('Location') == target['url'] + uri
            response.read()
        finally:
            conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('preflight', 'apply', 'verify'))
    args = parser.parse_args()
    assert os.geteuid() == 0
    registry = json.loads((ROOT / 'environments.json').read_text())
    ip = registry['listen_ip']
    interfaces = json.loads(subprocess.check_output(['ip', '-j', 'address', 'show'], text=True))
    assert ip in {item['local'] for interface in interfaces for item in interface.get('addr_info', [])}
    targets = registry['environments']
    capacity_delta = 0
    for target in targets.values():
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read(target['config'])
        options = cfg['options']
        minimum = target.get('min_db_connections', 0)
        if minimum:
            assert int(options.get('workers', '0')) == 0, 'Review worker/process capacity separately'
            capacity_delta += 2 * max(0, minimum - int(options.get('db_maxconn', '64')))
        assert int(options.get('http_port', options.get('xmlrpc_port', '8069'))) == target['port']
        if options.get('db_name') and options.get('db_name') != 'False':
            assert options.get('db_name') == target['database']
        run('systemctl', 'is-active', '--quiet', target['service'])
        login(target)
    if args.action == 'verify':
        for target in targets.values():
            redirect(ip, target)
            if target.get('deploy_enabled'):
                cfg = configparser.ConfigParser(interpolation=None)
                cfg.read(target['config'])
                assert cfg['options'].get('db_name') == target['database']
                assert cfg['options'].get('dbfilter') == '^' + re.escape(target['database']) + '$'
                assert cfg['options'].getboolean('list_db') is False
        print('CANONICAL_VERIFY_OK environments=' + str(len(targets)))
        return
    print('CANONICAL_PREFLIGHT_OK environments=' + str(len(targets)), flush=True)
    if args.action == 'preflight':
        return
    # Shared lease required by deployment runbooks for both coding agents.
    with open('/run/lock/steps-environments.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        upgrades = []
        for command in Path('/proc').glob('[0-9]*/cmdline'):
            try:
                argv = command.read_bytes().decode(errors='replace').split('\x00')
            except (OSError, PermissionError):
                continue
            for index, arg in enumerate(argv):
                if Path(arg).name == 'odoo-bin' and any(
                    option in ('-u', '-i', '--update', '--init') or option.startswith(('--update=', '--init='))
                    for option in argv[index + 1:]
                ):
                    upgrades.append(command.parent.name)
        assert not upgrades, 'An addon upgrade is already running; PIDs: ' + ', '.join(upgrades)
        if capacity_delta:
            limit = int(query('postgres', 'SHOW max_connections'))
            used = int(query('postgres', 'SELECT count(*) FROM pg_stat_activity'))
            assert used + capacity_delta + 10 < limit, 'Insufficient PostgreSQL connection reserve'
        backup = Path('/opt/steps_backups') / ('canonical_ports_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        backup.mkdir(mode=0o700, parents=True)
        originals = {}
        parameters = {}
        for name, target in targets.items():
            path = Path(target['config'])
            originals[name] = path.read_bytes()
            shutil.copy2(path, backup / path.name)
            if target['database']:
                parameters[name] = json.loads(query(target['database'], "SELECT COALESCE(json_agg(t),'[]'::json) FROM (SELECT key,value FROM ir_config_parameter WHERE key IN ('web.base.url','web.base.url.freeze')) t"))
        (backup / 'url_parameters.json').write_text(json.dumps(parameters, indent=2))
        old_site = SITE.read_bytes() if SITE.exists() else None
        old_enabled = ENABLED.exists()
        if old_site:
            (backup / 'nginx-site.conf').write_bytes(old_site)
        changed = []
        touched = []
        try:
            for name, target in targets.items():
                path = Path(target['config'])
                assert path.read_bytes() == originals[name], 'Concurrent config change: ' + name
                text = originals[name].decode()
                text = setting(text, 'http_interface', '127.0.0.1')
                text = setting(text, 'proxy_mode', 'True')
                if target.get('deploy_enabled'):
                    # Each active service belongs to exactly one customer/QA
                    # database; copied validation databases must never appear.
                    text = setting(text, 'db_name', target['database'])
                    text = setting(text, 'dbfilter', '^' + re.escape(target['database']) + '$')
                    text = setting(text, 'list_db', 'False')
                if target.get('min_db_connections'):
                    cfg = configparser.ConfigParser(interpolation=None)
                    cfg.read_string(text)
                    current = int(cfg['options'].get('db_maxconn', '64'))
                    text = setting(text, 'db_maxconn', str(max(current, target['min_db_connections'])))
                url_changed = False
                touched.append(name)
                if target['database']:
                    url_changed = {row['key']: row['value'] for row in parameters[name]} != {'web.base.url': target['url'], 'web.base.url.freeze': 'True'}
                    # Targets and URLs come only from the reviewed whitelist.
                    for key, value in (('web.base.url', target['url']), ('web.base.url.freeze', 'True')):
                        query(target['database'], "INSERT INTO ir_config_parameter (key,value,create_uid,write_uid,create_date,write_date) VALUES ('%s','%s',1,1,now(),now()) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value,write_date=now()" % (key, value))
                if text.encode() != originals[name] or url_changed:
                    path.write_text(text)
                    changed.append(name)
                    run('systemctl', 'restart', target['service'])
                    run('systemctl', 'is-active', '--quiet', target['service'])
            SITE.write_text('# Generated by tools/ops/canonical_ports.py; HTTPS upstreams remain local.\n' + '\n'.join(
                'server {\n    listen %s:%s;\n    server_name _;\n    return 308 %s$request_uri;\n}\n' % (ip, t['port'], t['url']) for t in targets.values()))
            if not ENABLED.exists():
                ENABLED.symlink_to(SITE)
            run('nginx', '-t')
            run('systemctl', 'reload', 'nginx')
            for target in targets.values():
                # systemctl reload returns before nginx's new workers bind.
                for attempt in range(15):
                    try:
                        redirect(ip, target)
                        break
                    except OSError:
                        if attempt == 14:
                            raise
                        time.sleep(1)
                for attempt in range(15):
                    try:
                        login(target)
                        break
                    except Exception:
                        if attempt == 14:
                            raise
                        time.sleep(2)
            result = {'backup': str(backup), 'restarted': changed, 'registry_sha256': hashlib.sha256((ROOT / 'environments.json').read_bytes()).hexdigest()}
            # Verify the observed startup burst, not just one sequential login.
            for target in targets.values():
                if target.get('min_db_connections'):
                    with ThreadPoolExecutor(max_workers=12) as pool:
                        list(pool.map(lambda _: login(target), range(12)))
            result['concurrent_logins'] = 12
            (backup / 'verified.json').write_text(json.dumps(result, indent=2))
            print('CANONICAL_APPLY_OK ' + json.dumps(result), flush=True)
        except Exception:
            if old_site is None:
                if not old_enabled:
                    ENABLED.unlink(missing_ok=True)
                SITE.unlink(missing_ok=True)
            else:
                SITE.write_bytes(old_site)
            for name in touched:
                target = targets[name]
                Path(target['config']).write_bytes(originals[name])
                if target['database']:
                    query(target['database'], "DELETE FROM ir_config_parameter WHERE key IN ('web.base.url','web.base.url.freeze')")
                for row in parameters.get(name, []):
                    query(target['database'], "INSERT INTO ir_config_parameter (key,value,create_uid,write_uid,create_date,write_date) VALUES ('%s','%s',1,1,now(),now())" % (row['key'], row['value'].replace("'", "''")))
                run('systemctl', 'restart', target['service'])
            run('nginx', '-t')
            run('systemctl', 'reload', 'nginx')
            print('CANONICAL_ROLLBACK backup=' + str(backup), flush=True)
            raise


if __name__ == '__main__':
    main()
