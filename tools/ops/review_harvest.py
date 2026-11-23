"""Review the exact Harvest build and native forms through a temporary read-only tunnel."""
import argparse
from contextlib import ExitStack
import configparser
import fcntl
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import time
from urllib.parse import unquote, urlsplit

from manage_management import query
from review_management_panel import is_read_request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('environment', choices=('development', 'cerro', 'qa-cerro'))
    parser.add_argument('--web-root', required=True, type=Path, help='Extracted immutable web release')
    parser.add_argument('--stage', type=Path, help='Certified private destination copy; omit for published review')
    parser.add_argument('--company-id', type=int)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--minutes', type=int, default=25)
    args = parser.parse_args()
    assert os.geteuid() == 0 and 1024 < args.port < 65536 and 1 <= args.minutes <= 30

    def abort_startup(*unused):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, abort_startup)
    tools = Path(__file__).resolve().parent
    target = json.loads((tools/'environments.json').read_text())['environments'][args.environment]
    config = configparser.ConfigParser(interpolation=None)
    config.read(target['config'])
    options = config['options']
    assert options['db_name'] == target['database']
    host = urlsplit(target['url']).hostname
    web = args.web_root.resolve()
    assert web.is_relative_to('/opt/steps-validation') and web == args.web_root
    frontend = json.loads((web/'release.json').read_text())
    assert frontend['repository'] == 'stepconsulting/step_harvest' and frontend['version'] == '0.0.3'
    for name, expected in frontend['files'].items():
        path = web/name
        assert path.resolve().is_relative_to(web) and not path.is_symlink()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
    database = target['database']
    source_options = []
    private_port = None
    stage = args.stage
    if stage:
        assert stage.resolve() == stage and stage.parent == Path('/opt/steps-validation')
        match = re.fullmatch(r'management_(development|cerro|qa-cerro)_t231232_([a-f0-9]{8})', stage.name)
        assert match and match[1] == args.environment
        proof = json.loads((stage/'qa_passed.json').read_text())
        database = proof['database']
        assert database == 'MANAGEMENT_QA_'+args.environment.upper()+'_t231232_'+match[2]
        assert proof['commit'].startswith(match[2])
        source_options = ['--addons-path='+str(stage/'addons')+','+options['addons_path'], '--data-dir='+str(stage/'data')]
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            private_port = listener.getsockname()[1]
    user = subprocess.check_output(['systemctl', 'show', '--value', '--property=User', target['service']], text=True).strip()
    odoo = ['sudo', '-u', user, '/usr/bin/python3.10', '/opt/odoo18/odoo-bin']
    common = ['-c', target['config'], '-d', database, '--db-filter=^'+database+'$',
        '--workers=0', '--max-cron-threads=0', *source_options]
    session_file = Path('/tmp/harvest-browser-%s.json' % os.getpid())
    session_script = """
import json
from pathlib import Path
from odoo import http
from native_business_profile import scoped_business_environment
proof=Path(SESSION_FILE)
if CLEANUP:
    saved=json.loads(proof.read_text())
    session=http.root.session_store.get(saved['session_id'])
    assert session.get('db')==env.cr.dbname
    http.root.session_store.delete(session)
    proof.unlink()
else:
    assert not proof.exists()
    company=env['res.company'].browse(COMPANY_ID).exists() if COMPANY_ID else None
    business=scoped_business_environment(env,company=company)
    user=business.user
    session=http.root.session_store.new()
    session.update({'db':env.cr.dbname,'uid':user.id,'login':user.login,
        'context':dict(user.with_user(user).context_get(),allowed_company_ids=business.company.ids),
        'session_token':user._compute_session_token(session.sid)})
    http.root.session_store.save(session)
    proof.write_text(json.dumps({'session_id':session.sid,'company_id':business.company.id}))
    proof.chmod(0o600)
env.cr.rollback()
print('HARVEST_REVIEW_SESSION_OK')
"""

    def session(cleanup=False):
        header = 'import sys\nsys.path.insert(0,'+repr(str(tools))+')\n'
        header += 'SESSION_FILE='+repr(str(session_file))+'\nCLEANUP='+repr(cleanup)+'\nCOMPANY_ID='+repr(args.company_id)+'\n'
        result = subprocess.run(odoo+['shell', *common, '--no-http', '--log-level=error'],
            input=header+session_script, text=True, capture_output=True)
        assert result.returncode == 0 and 'HARVEST_REVIEW_SESSION_OK' in result.stdout, result.stderr[-1200:]

    with ExitStack() as cleanup:
        lease = cleanup.enter_context(open('/run/lock/steps-environments.lock', 'a'))
        print('HARVEST_REVIEW_WAITING_FOR_LEASE', flush=True)
        fcntl.flock(lease, fcntl.LOCK_EX)
        if stage and args.environment == 'qa-cerro':
            from customer_qa_clone_access import clone_database_access
            cleanup.enter_context(clone_database_access(query, database, stage, existing=True))
        process = None
        if stage:
            command = odoo+common+['--http-interface=127.0.0.1', '--http-port='+str(private_port),
                '--smtp-server=127.0.0.1', '--smtp-port=1', '--logfile='+str(stage/'harvest-review-http.log')]
            process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

            def stop_backend():
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait(timeout=10)
            cleanup.callback(stop_backend)
            for attempt in range(90):
                assert process.poll() is None, 'Private Harvest review server stopped'
                try:
                    connection = http.client.HTTPConnection('127.0.0.1', private_port, timeout=2)
                    connection.request('GET', '/web/health', headers={'Host': host})
                    if connection.getresponse().status == 200:
                        connection.close()
                        break
                    connection.close()
                except OSError:
                    time.sleep(1)
            else:
                raise AssertionError('Private Harvest review server did not start')
        cleanup.callback(lambda: session(True) if session_file.exists() else None)
        session()
        auth = json.loads(session_file.read_text())

        class Proxy(BaseHTTPRequestHandler):
            def log_message(self, *unused):
                pass

            def forward(self):
                path = urlsplit(self.path).path
                length = int(self.headers.get('Content-Length', 0))
                if length > 2_000_000:
                    self.send_error(413)
                    return
                body = self.rfile.read(length) if length else b''
                if path == '/web/dataset/call_kw/iot.channel/get_iot_channel':
                    value = json.loads(body)
                    data = json.dumps({'jsonrpc': '2.0', 'id': value.get('id'), 'result': ''}).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                if self.command == 'GET' and stage and path.startswith('/cosecha/'):
                    name = 'app/'+unquote(path[len('/cosecha/'):]) if path != '/cosecha/' else 'app/index.html'
                    if name not in frontend['files']:
                        self.send_error(404)
                        return
                    data = (web/name).read_bytes()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/manifest+json' if name.endswith('.webmanifest') else mimetypes.guess_type(name)[0] or 'application/octet-stream')
                    self.send_header('Content-Length', str(len(data)))
                    self.send_header('Cache-Control', 'no-store')
                    self.end_headers()
                    self.wfile.write(data)
                    return
                if self.command == 'POST':
                    allowed = is_read_request(self.path, body)
                    try:
                        params = json.loads(body).get('params', {})
                        allowed |= params.get('model') == 'step.cosecha.registry' and params.get('method') == 'get_dashboard_data'
                        allowed |= params.get('model') in ('product.pricelist', 'product.pricelist.item') and params.get('method') in ('onchange', 'default_get')
                    except (ValueError, AttributeError):
                        pass
                    if not allowed or path == '/api/harvest/sync':
                        self.send_error(403, 'Read-only Harvest review')
                        return
                if self.command == 'GET' and not (path in ('/web', '/odoo', '/web/manifest.webmanifest', '/web/service-worker.js',
                    '/api/harvest/session', '/api/harvest/bootstrap', '/api/harvest/health') or
                    path.startswith(('/odoo/', '/cosecha/', '/web/assets/', '/web/image', '/web/content/', '/web/webclient/', '/bus/websocket_worker_bundle')) or '/static/' in path):
                    self.send_error(403, 'Read-only Harvest review')
                    return
                if path.startswith(('/web/login', '/web/database', '/websocket')):
                    self.send_error(403)
                    return
                headers = {name: value for name, value in self.headers.items() if name.lower() not in ('cookie', 'host', 'connection', 'accept-encoding')}
                headers.update({'Host': host, 'Cookie': 'session_id='+auth['session_id'], 'X-Forwarded-Proto': 'https', 'Connection': 'close'})
                connection = http.client.HTTPConnection('127.0.0.1', private_port, timeout=90) if stage else http.client.HTTPSConnection(host, timeout=90)
                try:
                    connection.request(self.command, self.path, body=body or None, headers=headers)
                    response = connection.getresponse()
                    data = response.read()
                    self.send_response(response.status)
                    for name, value in response.getheaders():
                        if name.lower() not in ('set-cookie', 'content-length', 'transfer-encoding', 'connection'):
                            self.send_header(name, value)
                    self.send_header('Content-Length', str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                finally:
                    connection.close()

            do_GET = forward
            do_POST = forward

        class ReviewServer(ThreadingHTTPServer):
            daemon_threads = True
        server = ReviewServer(('127.0.0.1', args.port), Proxy)
        cleanup.callback(server.server_close)
        server.timeout = 1
        stopped = False

        def stop(*unused):
            nonlocal stopped
            stopped = True
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        print('HARVEST_REVIEW_READY '+json.dumps({'url': 'http://127.0.0.1:%s/cosecha/' % args.port,
            'environment': args.environment, 'database': database, 'company_id': auth['company_id'],
            'web_commit': frontend['commit'], 'read_only': True}), flush=True)
        deadline = time.monotonic()+args.minutes*60
        while not stopped and time.monotonic() < deadline:
            server.handle_request()
    print('HARVEST_REVIEW_REMOVED', flush=True)


if __name__ == '__main__':
    main()
