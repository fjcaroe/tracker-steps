"""Review an exact Harvest build through a temporary, restricted private tunnel."""
import argparse
from contextlib import ExitStack
import configparser
import fcntl
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
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
from review_management_panel import is_read_request, is_action_breadcrumb_read
from harvest_web_policy import (SUPPORTED_VERSIONS, require_authorized_environment,
                                validate_static_copy, require_copy_sync_certificate,
                                is_copy_sync_request, OPERATIONS_WRITE_PATHS,
                                validate_operations_copy)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('environment', choices=('development', 'cerro', 'qa-cerro'))
    parser.add_argument('--web-root', required=True, type=Path, help='Extracted immutable web release')
    parser.add_argument('--stage', type=Path, help='Certified private destination copy; omit for published review')
    parser.add_argument('--company-id', type=int)
    parser.add_argument('--user-id', type=int, help='Review one existing internal user without changing credentials or permissions')
    parser.add_argument('--multi-company', action='store_true', help='Prefer an existing business editor already authorized in several companies')
    parser.add_argument('--allow-copy-sync', action='store_true', help='Allow exact same-origin Harvest API writes only in a certified private copy')
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--minutes', type=int, default=25)
    args = parser.parse_args()
    assert os.geteuid() == 0 and 1024 < args.port < 65536 and 1 <= args.minutes <= 30
    assert args.user_id is None or args.user_id > 1, 'Select an existing non-superuser profile'
    assert args.company_id is None or args.company_id > 0, 'Select an existing company'
    assert not args.allow_copy_sync or args.stage is not None, 'Sync testing requires a certified private copy'

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
    assert frontend['repository'] == 'stepconsulting/step_harvest' and frontend['version'] in SUPPORTED_VERSIONS
    require_authorized_environment(frontend, args.environment)
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
        match = re.fullmatch(r'management_(development|cerro|qa-cerro)_(t231232|harvestcompany|harvestandroid|t233|t234|t235|t236237)_([a-f0-9]{8})', stage.name)
        assert match and match[1] == args.environment
        proof = json.loads((stage/'qa_passed.json').read_text())
        database = proof['database']
        assert database == 'MANAGEMENT_QA_'+args.environment.upper()+'_'+match[2]+'_'+match[3]
        if match[2] in ('harvestcompany', 'harvestandroid'):
            validate_static_copy(frontend, args.environment, stage.name, proof)
        else:
            assert proof['commit'].startswith(match[3])
        if frontend['version'] == '0.0.8':
            validate_operations_copy(frontend, args.environment, stage.name, proof)
        if args.allow_copy_sync:
            require_copy_sync_certificate(frontend, args.environment, stage.name, proof)
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
    assert COMPANY_ID is None or len(company)==1, 'The requested company no longer exists'
    business=(scoped_existing_user_environment(env,USER_ID,company=company) if USER_ID
              else scoped_business_environment(env,company=company))
    if MULTI_COMPANY and not USER_ID:
        editors=env['res.users'].search([('active','=',True),('share','=',False),('id','!=',1),
            ('company_ids','in',business.company.ids)],order='id').filtered(lambda user:
                len(user.company_ids)>1 and user.has_group('base.group_system') and user.has_group('account.group_account_manager'))
        assert editors, 'Existing multi-company business editor required; do not grant permissions'
        business=env(user=editors[:1],su=False,context=dict(env.context,allowed_company_ids=business.company.ids))
    elif MULTI_COMPANY:
        assert len(business.user.company_ids)>1, 'The requested existing user is not authorized in several companies'
    user=business.user
    session=http.root.session_store.new()
    session.update({'db':env.cr.dbname,'uid':user.id,'login':user.login,
        'context':dict(user.with_user(user).context_get(),allowed_company_ids=business.company.ids),
        'session_token':user._compute_session_token(session.sid)})
    http.root.session_store.save(session)
    actions=[]
    for xmlid in ('step_cosecha.action_step_cosecha_dashboard',
            'step_cosecha_operations.action_harvest_dashboard_settings',
            'step_cosecha.action_step_cosecha_costo_pro',
            'step_cosecha.action_step_cosecha_registry_costo',
            'step_cosecha.action_step_cosecha_registry',
            'step_cosecha.action_step_cosecha_registry_contra',
            'step_harvest_launcher.harvest_attendance_own',
            'step_harvest_launcher.harvest_attendance_contractor'):
        action=env.ref(xmlid,raise_if_not_found=False)
        if action:
            assert action._name in ('ir.actions.client','ir.actions.act_window')
            actions.append(action.id)
    proof.write_text(json.dumps({'session_id':session.sid,'company_id':business.company.id,'user_id':user.id,
        'breadcrumb_actions':actions}))
    proof.chmod(0o600)
env.cr.rollback()
print('HARVEST_REVIEW_SESSION_OK')
"""

    def session(cleanup=False):
        # The tool bundle remains private to root. Pass this versioned helper
        # as shell input rather than widening access to the bundle directory.
        header = (tools/'native_business_profile.py').read_text()+'\n'
        header += 'SESSION_FILE='+repr(str(session_file))+'\nCLEANUP='+repr(cleanup)+'\nCOMPANY_ID='+repr(args.company_id)+'\nUSER_ID='+repr(args.user_id)+'\nMULTI_COMPANY='+repr(args.multi_company or frontend['version'] == '0.0.4')+'\n'
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
                '--smtp=127.0.0.1', '--smtp-port=1', '--logfile='+str(stage/'harvest-review-http.log')]
            launch_log = stage/'harvest-review-launch.log'
            launch_output = cleanup.enter_context(launch_log.open('a'))
            process = subprocess.Popen(command, stdout=launch_output, stderr=subprocess.STDOUT, start_new_session=True)

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
                assert process.poll() is None, 'Private Harvest review server stopped: '+launch_log.read_text()[-1200:]
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
        review_policy = {'environment': args.environment, 'database': database,
            'web_commit': frontend['commit'], 'company_id': auth['company_id'],
            'harvest_web': frontend,
            'user_id': auth['user_id'], 'read_only': not args.allow_copy_sync,
            'copy_sync_allowed': args.allow_copy_sync,
            'sync_origin': 'http://127.0.0.1:'+str(args.port) if args.allow_copy_sync else None}
        if stage:
            policy_file = stage/'harvest-review-policy.json'
            policy_file.write_text(json.dumps(review_policy, indent=2))
            policy_file.chmod(0o600)

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
                    copy_sync = is_copy_sync_request(args.allow_copy_sync, self.command,
                        self.path, self.headers.get('Origin'), args.port, frontend['version'])
                    allowed = is_read_request(self.path, body) or path == '/web/session/get_session_info'
                    if path == '/web/action/load_breadcrumbs':
                        allowed = is_action_breadcrumb_read(body, auth['breadcrumb_actions'], ('step.cosecha.registry', 'hr.attendance'))
                    try:
                        params = json.loads(body).get('params', {})
                        allowed |= params.get('model') == 'step.cosecha.registry' and params.get('method') == 'get_dashboard_data'
                        # Native initial forms need defaults/onchanges; persistence
                        # (web_save/execute) remains blocked in the review proxy.
                        allowed |= params.get('model') in ('product.pricelist', 'product.pricelist.item', 'res.config.settings') and params.get('method') in ('onchange', 'default_get')
                    except (ValueError, AttributeError):
                        pass
                    if path in OPERATIONS_WRITE_PATHS:
                        allowed = copy_sync
                    if not allowed:
                        self.send_error(403, 'Harvest review request not allowed')
                        return
                if self.command == 'GET' and not (path in ('/web', '/odoo', '/harvest/open', '/web/manifest.webmanifest', '/web/service-worker.js',
                    '/api/harvest/session', '/api/harvest/bootstrap', '/api/harvest/health',
                    '/api/harvest/ref/jobs') or
                    path.startswith(('/odoo/', '/cosecha/', '/web/assets/', '/web/image', '/web/content/', '/web/webclient/', '/bus/websocket_worker_bundle')) or '/static/' in path):
                    self.send_error(403, 'Read-only Harvest review')
                    return
                if path.startswith(('/web/login', '/web/database', '/websocket')):
                    self.send_error(403)
                    return
                headers = {name: value for name, value in self.headers.items() if name.lower() not in ('cookie', 'host', 'connection', 'accept-encoding')}
                cookies = SimpleCookie(self.headers.get('Cookie', ''))
                selected = cookies['cids'].value if 'cids' in cookies else str(auth['company_id'])
                if not re.fullmatch(r'[0-9]+(?:[-,][0-9]+)*', selected):
                    self.send_error(400, 'Invalid company cookie')
                    return
                headers.update({'Host': host, 'Cookie': 'session_id='+auth['session_id']+'; cids='+selected, 'X-Forwarded-Proto': 'https', 'Connection': 'close'})
                if self.command == 'POST' and path in OPERATIONS_WRITE_PATHS:
                    headers['Origin'] = 'https://'+host
                connection = http.client.HTTPConnection('127.0.0.1', private_port, timeout=90) if stage else http.client.HTTPSConnection(host, timeout=90)
                try:
                    connection.request(self.command, self.path, body=body or None, headers=headers)
                    response = connection.getresponse()
                    data = response.read()
                    self.send_response(response.status)
                    for name, value in response.getheaders():
                        if name.lower() not in ('set-cookie', 'content-length', 'transfer-encoding', 'connection'):
                            if name.lower() == 'location':
                                redirect = urlsplit(value)
                                if redirect.hostname == host:
                                    value = redirect.path + ('?' + redirect.query if redirect.query else '')
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
            **review_policy}), flush=True)
        deadline = time.monotonic()+args.minutes*60
        while not stopped and time.monotonic() < deadline:
            server.handle_request()
    print('HARVEST_REVIEW_REMOVED', flush=True)


if __name__ == '__main__':
    main()
