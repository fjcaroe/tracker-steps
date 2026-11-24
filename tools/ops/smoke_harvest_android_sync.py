"""Exercise one native Harvest upload and retry only in a certified private copy.

The loopback review proxy supplies its temporary session. This tool never reads
credentials, sends a session ID, changes masters, or targets a published host.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import uuid

from harvest_web_policy import require_copy_sync_certificate


def review_origin(url):
    parsed = urlsplit(url)
    assert (parsed.scheme == 'http' and parsed.hostname == '127.0.0.1'
            and parsed.port and 1024 < parsed.port < 65536
            and parsed.path in ('', '/') and not parsed.query
            and not parsed.fragment and not parsed.username and not parsed.password), \
        'Use only the exact loopback Harvest review proxy URL'
    return 'http://127.0.0.1:' + str(parsed.port)


def validate_review_policy(origin, stage_name, proof, policy):
    frontend = proof['harvest_web']
    require_copy_sync_certificate(frontend, 'development', stage_name, proof)
    assert policy['environment'] == 'development'
    assert policy['database'] == proof['database']
    assert policy['web_commit'] == frontend['commit']
    assert policy['read_only'] is False and policy['copy_sync_allowed'] is True
    assert policy['sync_origin'] == origin
    assert positive_id(policy['user_id']) and policy['user_id'] > 1
    assert positive_id(policy['company_id'])


def positive_id(value):
    return type(value) is int and value > 0


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, url):
        raise AssertionError('The private review proxy unexpectedly redirected a smoke request')


class ReviewClient:
    def __init__(self, origin):
        self.origin = review_origin(origin)
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def request(self, method, path, payload=None):
        assert (method, path) in (
            ('GET', '/api/harvest/session'), ('GET', '/api/harvest/bootstrap'),
            ('GET', '/api/harvest/health'), ('POST', '/api/harvest/sync'))
        headers = {'Cache-Control': 'no-cache'}
        data = None
        if payload is not None:
            assert method == 'POST' and path == '/api/harvest/sync'
            headers.update({'Origin': self.origin, 'Content-Type': 'application/json'})
            data = json.dumps(payload, separators=(',', ':')).encode()
        request = urllib.request.Request(self.origin + path, data=data,
            headers=headers, method=method)
        try:
            response = self.opener.open(request, timeout=120)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            status = response.status
            body = response.read(2_000_001)
            assert len(body) <= 2_000_000, 'Unexpected review response size'
            assert 'application/json' in response.headers.get('Content-Type', ''), \
                'The review proxy did not return the expected JSON API response'
        try:
            result = json.loads(body)
        except (ValueError, UnicodeError):
            raise AssertionError('The review proxy returned invalid API JSON') from None
        assert isinstance(result, dict), 'The review proxy returned an invalid API object'
        return status, result


def require_success(status, data, label):
    assert status == 200 and data.get('ok') is True, label + ' failed; inspect private server logs'


def exercise_sync(client, policy, run_uuid=None):
    status, session = client.request('GET', '/api/harvest/session')
    require_success(status, session, 'Native session')
    assert session.get('connected') is True, 'The private review session is not connected'
    status, health = client.request('GET', '/api/harvest/health')
    require_success(status, health, 'Native health')
    assert 'context_scope' in health.get('capabilities', []), 'The scoped Harvest backend is required'
    status, bootstrap = client.request('GET', '/api/harvest/bootstrap')
    require_success(status, bootstrap, 'Native bootstrap')
    for data in (session, bootstrap):
        assert data['user']['id'] == policy['user_id'], 'The proxy profile changed'
        assert data['company']['id'] == policy['company_id'], 'The proxy company changed'
    scope = bootstrap['scope']
    assert isinstance(scope, str) and re.fullmatch('[a-f0-9]{64}', scope)
    assert session['scope'] == health['scope'] == scope, 'The native context changed during bootstrap'
    workers = [row for row in bootstrap['workers'] if positive_id(row.get('id'))]
    orders = [row for row in bootstrap['orders'] if positive_id(row.get('odoo_id'))]
    assert workers and orders, 'The selected company needs an existing accessible worker and native OT'
    order = next((row for row in orders if row.get('status') == 'En proceso'), orders[0])
    run_uuid = run_uuid or 'QA-HARVEST-ANDROID-' + uuid.uuid4().hex
    assert re.fullmatch(r'QA-HARVEST-ANDROID-[a-f0-9]{32}', run_uuid)
    record = {'client_uuid': run_uuid, 'worker_id': workers[0]['id'],
        'work_order': {'odoo_id': order['odoo_id']}, 'tarja': 'QA-ANDROID-' + run_uuid[-12:],
        'row': 'QA-ANDROID', 'boxes': 1, 'kilos': 1,
        'event_datetime': datetime.now(timezone.utc).isoformat()}
    altered_scope = ('f' if scope[0] != 'f' else 'e') + scope[1:]
    status, rejected = client.request('POST', '/api/harvest/sync',
        {'scope': altered_scope, 'records': [record]})
    assert status == 409 and rejected.get('ok') is False, 'A changed scope must be rejected before upload'
    payload = {'scope': scope, 'records': [record]}
    status, first = client.request('POST', '/api/harvest/sync', payload)
    require_success(status, first, 'Native copy upload')
    results = first.get('results')
    assert isinstance(results, list) and len(results) == 1, 'Expected exactly one upload result'
    created = results[0]
    assert created.get('ok') is True and created.get('duplicate') is False, 'The fresh QA UUID must create exactly one native line'
    assert created.get('client_uuid') == run_uuid and positive_id(created.get('id'))
    assert created.get('work_order_id') == order['odoo_id'], 'The line must use the selected existing native OT'
    status, second = client.request('POST', '/api/harvest/sync', payload)
    require_success(status, second, 'Native retry')
    results = second.get('results')
    assert isinstance(results, list) and len(results) == 1, 'Expected exactly one retry result'
    repeated = results[0]
    assert (repeated.get('ok') is True and repeated.get('duplicate') is True
            and repeated.get('client_uuid') == run_uuid and repeated.get('id') == created['id']), \
        'Retry must return the same native line as a duplicate'
    return {'run_uuid': run_uuid, 'native_context': True,
        'scope_rejected_before_write': True, 'rejected_scope_http_status': 409,
        'native_copy_sync': True, 'sync_idempotency': True,
        'first_write_duplicate': False, 'retry_duplicate': True, 'same_native_line': True,
        'native_line_id': created['id'], 'new_lines': 1,
        'worker_catalog_count': len(workers), 'native_order_catalog_count': len(orders),
        'existing_relations_only': True, 'credentials_or_session_ids_supplied': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--stage', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--ready-seconds', type=int, default=0)
    args = parser.parse_args()
    origin = review_origin(args.url)
    stage = args.stage
    assert stage.resolve() == stage and stage.parent == Path('/opt/steps-validation') and not stage.is_symlink()
    proof = json.loads((stage/'qa_passed.json').read_text())
    policy = json.loads((stage/'harvest-review-policy.json').read_text())
    validate_review_policy(origin, stage.name, proof, policy)
    output = args.output
    assert output.is_absolute() and output.resolve() == output and not output.exists(), \
        'Use a fresh external evidence file'
    assert not output.is_relative_to(Path(__file__).resolve().parent), 'Keep evidence outside the versioned tools'
    assert not any((parent/'.git').exists() for parent in output.parents), 'Keep evidence outside Git checkouts'
    assert 0 <= args.ready_seconds <= 300
    client = ReviewClient(origin)
    deadline = time.monotonic() + args.ready_seconds
    while True:
        try:
            client.request('GET', '/api/harvest/session')
            break
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(2)
    evidence = exercise_sync(client, policy)
    evidence.update({'feature': proof['feature'], 'stage': stage.name,
        'database': proof['database'], 'web_commit': proof['harvest_web']['commit'],
        'backend_commit': proof['commit'], 'backend_sha256': proof['release_sha256'],
        'created_at': datetime.now(timezone.utc).isoformat()})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    output.chmod(0o600)
    print('HARVEST_ANDROID_COPY_SYNC_OK ' + json.dumps(evidence, sort_keys=True))


if __name__ == '__main__':
    main()
