"""Read-only native-company contract probe against a private Harvest review proxy."""
import argparse
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ready-seconds', type=int, default=0)
    args = parser.parse_args()
    url = urlsplit(args.url)
    assert url.scheme == 'http' and url.hostname == '127.0.0.1' and url.port
    assert url.path in ('', '/') and not url.query and not url.username
    assert 0 <= args.ready_seconds <= 300
    root = args.url.rstrip('/')

    def read(path, company=None, rpc=False):
        headers = {'Cache-Control': 'no-cache'}
        if company is not None:
            headers['Cookie'] = 'cids=' + str(company)
        data = None
        if rpc:
            headers['Content-Type'] = 'application/json'
            data = json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': {}}).encode()
        request = urllib.request.Request(root + path, data=data, headers=headers)
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.load(response)
        if rpc:
            assert 'error' not in result
            result = result['result']
        return result

    deadline = time.monotonic() + args.ready_seconds
    while True:
        try:
            session = read('/api/harvest/session')
            break
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(2)
    assert session['connected'] and session['user']['id']
    native = read('/web/session/get_session_info', rpc=True)
    assert native['uid'] == session['user']['id']
    allowed = native['user_companies']['allowed_companies']
    assert len(allowed) > 1, 'An existing multi-company editor is required'
    companies, scopes = [], set()
    for key, company in allowed.items():
        company_id = int(key)
        assert company_id == company['id'] and company_id > 0
        selected = read('/api/harvest/session', company_id)
        bootstrap = read('/api/harvest/bootstrap', company_id)
        assert selected['connected'] and selected['user']['id'] == native['uid']
        assert selected['company']['id'] == bootstrap['company']['id'] == company_id
        assert bootstrap['user']['id'] == native['uid']
        assert selected['scope'] == bootstrap['scope'] and bootstrap['scope'] not in scopes
        scopes.add(bootstrap['scope'])
        companies.append({'id': company_id, 'name': company['name'],
            'orders': len(bootstrap['orders']), 'workers': len(bootstrap['workers'])})
    proof = {'native_uid': native['uid'], 'companies': companies,
        'native_identity_and_company_scope': True, 'read_only': True}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(proof, indent=2), encoding='utf-8')
    print('HARVEST_COMPANY_CONTEXT_OK ' + json.dumps(proof))


if __name__ == '__main__':
    main()
