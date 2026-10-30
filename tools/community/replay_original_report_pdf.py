"""Replay captured private HTML/assets through wkhtmltopdf without Odoo or SQL.

This is a diagnostic experiment, never acceptance of payroll or a legal layout.
Only original static assets are served on loopback. No cookies are captured or
needed: the real normal-actor authorization happened in the functional test.
"""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import shutil
import subprocess
import threading
from urllib.parse import urlsplit


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def checked(root, entry):
    name = entry['file']
    if not isinstance(name, str) or Path(name).is_absolute():
        raise ValueError('Captured filenames must be relative')
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('Captured file escapes the evidence directory or is missing')
    raw = path.read_bytes()
    if sha(raw) != entry['sha256'] or len(raw) != entry['bytes']:
        raise ValueError('Captured bytes differ from their receipt')
    return raw


def variant_arguments(original, spacing=None, delay=None):
    value = list(original)
    for name, override in (('--header-spacing', spacing), ('--javascript-delay', delay)):
        if override is None:
            continue
        if value.count(name) != 1 or value.index(name) + 1 == len(value):
            raise ValueError('A diagnostic override needs one existing option: ' + name)
        value[value.index(name) + 1] = str(override)
    if '--disable-local-file-access' not in value or any(
            option in value for option in ('--cookie', '--cookie-jar', '--post', '--post-file', '--run-script')):
        raise ValueError('Replay must retain local-file protection and omit credentials or active payloads')
    return value


def rewrite_base(raw, url):
    matches = re.findall(rb'<base\s+href="(http://127\.0\.0\.1:[0-9]+)/?"\s*/?>', raw)
    if len(matches) != 1:
        raise ValueError('Exactly one original loopback base URL is required')
    return raw.replace(matches[0], url.encode('ascii')), matches[0].decode('ascii')


def write(path, raw):
    with path.open('xb') as handle:
        handle.write(raw)
    path.chmod(0o600)
    return {'file': path.name, 'sha256': sha(raw), 'bytes': len(raw)}


def replay(evidence, output, executable, repetition=1, repeats=3, spacing=None, delay=None):
    evidence, output = Path(evidence), Path(output)
    proof_raw = (evidence / 'proof.json').read_bytes()
    proof = json.loads(proof_raw)
    if not 1 <= repetition <= len(proof['repetitions']) or not 1 <= repeats <= 5:
        raise ValueError('A captured repetition and one to five diagnostic replays are required')
    selected = proof['repetitions'][repetition - 1]
    pipeline_entry = {'file': selected['pipeline'], 'sha256': selected['pipeline_sha256'],
                      'bytes': selected['pipeline_bytes']}
    pipeline_raw = checked(evidence, pipeline_entry)
    pipeline = json.loads(pipeline_raw)
    if any(len(pipeline[key]) != 1 for key in ('run_calls', 'argument_calls', 'prepare_calls')):
        raise ValueError('Replay requires one real captured pipeline')
    run, arguments = pipeline['run_calls'][0], pipeline['argument_calls'][0]
    pipeline_root = evidence / Path(selected['pipeline']).parent
    bodies = [checked(pipeline_root, item) for item in run['bodies']]
    header, footer = checked(pipeline_root, run['header']), checked(pipeline_root, run['footer'])
    asset_raw = checked(evidence, proof['asset_capture'])
    assets = json.loads(asset_raw)
    cache = {}
    for url, item in assets.items():
        if not url.startswith('/') or urlsplit(url).netloc:
            raise ValueError('Only original relative static resource URLs may be replayed')
        cache[url] = checked(evidence, item), item['content_type']
    if {key: sha(value[0]) for key, value in cache.items()} != proof['runtime_asset_sha256']:
        raise ValueError('Captured assets differ from the functional sidecar fingerprint')
    missing, requested = [], []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            key = urlsplit(self.path).path
            if key not in cache:
                missing.append(key)
                self.send_error(404)
                return
            raw, mime = cache[key]
            requested.append(key)
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):
            pass

    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = 'http://127.0.0.1:%s' % server.server_port
    files, rewrites = [], []
    for name, raw in [('report.header.tmp.replay.html', header), ('report.footer.tmp.replay.html', footer),
                      *[('report.body.tmp.%s.replay.html' % index, body) for index, body in enumerate(bodies)]]:
        modified, origin = rewrite_base(raw, base)
        write(output / name, modified)
        files.append(output / name)
        rewrites.append({'file': name, 'original_sha256': sha(raw), 'rewritten_sha256': sha(modified),
                         'original_base': origin, 'replay_base': base,
                         'transformation': 'Only captured loopback origin substituted; resource bytes unchanged'})
    effective = variant_arguments(arguments['arguments'], spacing, delay)
    receipt = {'schema': 'original-report-static-replay-v1', 'diagnostic_only': True,
               'technical_headers_accepted': False, 'productive_layout_accepted': False,
               'legal_validity_certified': False, 'proof_sha256': sha(proof_raw),
               'pipeline_sha256': sha(pipeline_raw), 'assets_manifest_sha256': sha(asset_raw),
               'tool_sha256': sha(Path(__file__).read_bytes()), 'captured_arguments': arguments['arguments'],
               'effective_arguments': effective, 'experimental_overrides': {'spacing': spacing, 'delay': delay},
               'session_or_cookie_arguments_used': False, 'rewrites': rewrites, 'runs': []}
    try:
        version = subprocess.run([executable, '--version'], check=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, timeout=15).stdout.decode('utf-8', 'replace').strip()
        receipt['wkhtmltopdf_version'] = version
        for index in range(1, repeats + 1):
            target = output / ('replay-%s.pdf' % index)
            command = [executable, *effective, '--header-html', str(files[0]), '--footer-html', str(files[1]),
                       *map(str, files[2:]), str(target)]
            process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
            if process.returncode not in (0, 1) or not target.exists() or not target.read_bytes().startswith(b'%PDF-'):
                raise RuntimeError('Real wkhtmltopdf replay did not produce a PDF')
            target.chmod(0o600)
            raw = target.read_bytes()
            receipt['runs'].append({'file': target.name, 'sha256': sha(raw), 'bytes': len(raw),
                                    'returncode': process.returncode,
                                    'stderr': process.stderr.decode('utf-8', 'replace')[-3000:]})
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)
        receipt['missing_assets'] = sorted(set(missing))
        receipt['requested_assets'] = sorted(set(requested))
        write(output / 'replay.json', json.dumps(receipt, indent=2, sort_keys=True).encode('utf-8') + b'\n')
    if missing:
        raise RuntimeError('Replay requested uncaptured assets')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--wkhtmltopdf', default=shutil.which('wkhtmltopdf'))
    parser.add_argument('--repetition', type=int, default=1)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--header-spacing', type=float)
    parser.add_argument('--javascript-delay', type=int)
    args = parser.parse_args()
    if not args.wkhtmltopdf:
        parser.error('An existing wkhtmltopdf executable is required; this tool installs nothing')
    result = replay(args.evidence, args.output, args.wkhtmltopdf, args.repetition,
                    args.repeats, args.header_spacing, args.javascript_delay)
    print(json.dumps({'diagnostic_only': True, 'runs': len(result['runs']), 'missing_assets': result['missing_assets']}))


if __name__ == '__main__':
    main()
