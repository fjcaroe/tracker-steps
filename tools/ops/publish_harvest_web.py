"""Publish an immutable, browser-reviewed Harvest build to one isolated vhost."""
import argparse
import configparser
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import time
import urllib.error
import urllib.request
from harvest_web_policy import (SUPPORTED_VERSIONS, require_authorized_environment,
                                validate_android_review, validate_static_copy,
                                validate_operations_review, validate_operations_smokes)

HOSTS = {'development': 'desarrollo.stepsapp.cl', 'cerro': 'cerroelplomo.stepsapp.cl',
         'qa-cerro': 'qa-cerroelplomo.stepsapp.cl'}
CONFIGS = {'development': '/etc/nginx/sites-enabled/stepsapp',
           'cerro': '/etc/nginx/sites-enabled/cerroelplomo.stepsapp.cl',
           'qa-cerro': '/etc/nginx/sites-enabled/qa-cerroelplomo.stepsapp.cl'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def end_block(source, opening):
    depth, quote, comment, escaped = 0, '', False, False
    for index in range(opening, len(source)):
        char = source[index]
        if comment:
            if char == '\n':
                comment = False
            continue
        if quote:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == quote:
                quote = ''
            continue
        if char == '#':
            comment = True
        elif char in ('"', "'"):
            quote = char
        elif char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return index + 1
    raise ValueError('Unbalanced nginx block')


def patch_config(source, host, root):
    candidates = []
    for match in re.finditer(r'(?m)^\s*server\s*\{', source):
        opening = source.index('{', match.start())
        end = end_block(source, opening)
        block = source[match.start():end]
        names = re.search(r'\bserver_name\s+([^;]+);', block)
        if names and host in names[1].split() and re.search(r'\blisten\s+[^;]*\b443\b', block):
            candidates.append((match.start(), end, block))
    assert len(candidates) == 1, 'Require one exact TLS vhost'
    start, end, block = candidates[0]
    locations = []
    for match in re.finditer(r'(?m)^\s*location\s+(?:=\s*|\^~\s*)?/cosecha(?=[/\s{])[^\n{]*\{', block):
        closing = end_block(block, block.index('{', match.start()))
        locations.append((match.start(), closing))
    assert len(locations) in (2, 5), 'Unexpected Harvest routing baseline'
    for left, right in reversed(locations):
        block = block[:left] + block[right:]
    snippet = '''
    # Steps Harvest: isolated immutable build
    location = /cosecha { return 301 /cosecha/; }
    location = /cosecha/manifest.webmanifest {
        alias ROOT/manifest.webmanifest;
        default_type application/manifest+json;
        add_header Cache-Control "no-cache";
    }
    location = /cosecha/sw.js {
        alias ROOT/sw.js;
        default_type application/javascript;
        add_header Cache-Control "no-cache";
        add_header Service-Worker-Allowed "/cosecha/";
    }
    location ^~ /cosecha/assets/ {
        alias ROOT/assets/;
        add_header Cache-Control "public, max-age=31536000, immutable";
    }
    location ^~ /cosecha/ {
        alias ROOT/;
        index index.html;
        try_files $uri $uri/ /cosecha/index.html;
        add_header Cache-Control "no-cache";
    }
'''.replace('ROOT', str(root))
    block = block[:-1] + snippet + '}'
    return source[:start] + block + source[end:]


def validate(web):
    manifest = json.loads((web/'release.json').read_text())
    assert manifest['repository'] == 'stepconsulting/step_harvest'
    assert re.fullmatch('[a-f0-9]{40}', manifest['commit']) and manifest['version'] in SUPPORTED_VERSIONS
    assert len(manifest['files']) == 5
    for name, expected in manifest['files'].items():
        path = web/name
        assert name.startswith('app/') and path.resolve().is_relative_to(web) and not path.is_symlink()
        assert sha(path) == expected, name
    return manifest


def extract(package, web):
    assert not web.exists() and web.parent.resolve().is_relative_to('/opt/steps-validation')
    with tarfile.open(package, 'r:gz') as archive:
        for member in archive.getmembers():
            assert member.isfile() and not member.issym() and not member.islnk()
            assert (web/member.name).resolve().is_relative_to(web)
            assert member.name == 'release.json' or member.name.startswith('app/')
        web.mkdir(mode=0o755)
        archive.extractall(web)
    return validate(web)


def public_hashes(host, manifest, attempts=1):
    # nginx reload returns before its new workers have taken over. Require the
    # entire immutable package, allowing only a bounded handover after reload.
    assert 1 <= attempts <= 20
    for attempt in range(attempts):
        hashes = {}
        try:
            for name, expected in manifest['files'].items():
                url = 'https://'+host+'/cosecha/'+name.removeprefix('app/')
                response = urllib.request.urlopen(urllib.request.Request(url, headers={'Cache-Control': 'no-cache'}), timeout=40)
                hashes[name] = hashlib.sha256(response.read()).hexdigest()
                assert hashes[name] == expected, url
                if name.endswith(('index.html', 'sw.js', 'manifest.webmanifest')):
                    assert 'no-cache' in response.headers.get('Cache-Control', ''), url
            return hashes
        except (OSError, urllib.error.URLError, AssertionError):
            if attempt + 1 == attempts:
                raise
            time.sleep(0.5)


def current_javascript_hash(host):
    base = 'https://'+host
    request = urllib.request.Request(base+'/cosecha/', headers={'Cache-Control': 'no-cache'})
    html = urllib.request.urlopen(request, timeout=40).read().decode('utf-8')
    scripts = re.findall(r'<script\b[^>]*\bsrc="([^"]+\.js)"', html)
    assert len(scripts) == 1 and scripts[0].startswith('/cosecha/assets/')
    assert '..' not in scripts[0] and '://' not in scripts[0]
    return hashlib.sha256(urllib.request.urlopen(base+scripts[0], timeout=40).read()).hexdigest()


def main():
    import fcntl
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('extract', 'deploy', 'verify'))
    parser.add_argument('environment', choices=tuple(HOSTS))
    parser.add_argument('--web', required=True, type=Path)
    parser.add_argument('--package', type=Path)
    parser.add_argument('--stage', type=Path)
    parser.add_argument('--expected-js-sha256', help='Observed pre-deployment build; reject concurrent static changes')
    args = parser.parse_args()
    assert os.geteuid() == 0
    web = args.web
    assert web.resolve() == web and web.is_relative_to('/opt/steps-validation')
    if args.action == 'extract':
        manifest = extract(args.package, web)
        require_authorized_environment(manifest, args.environment)
        print('HARVEST_WEB_EXTRACTED '+json.dumps(manifest))
        return
    manifest = validate(web)
    require_authorized_environment(manifest, args.environment)
    target = json.loads((Path(__file__).parent/'environments.json').read_text())['environments'][args.environment]
    assert target['url'].rstrip('/') == 'https://'+HOSTS[args.environment]
    with open('/run/lock/steps-environments.lock', 'a') as lease:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action == 'verify':
            print('HARVEST_WEB_SERVED_OK '+json.dumps(public_hashes(HOSTS[args.environment], manifest)))
            return
        stage = args.stage
        assert stage.resolve() == stage and stage.parent == Path('/opt/steps-validation')
        passed = json.loads((stage/'qa_passed.json').read_text())
        review = json.loads((stage/'harvest-browser-proof.json').read_text())
        assert review['reviewed'] is True and review['web_commit'] == manifest['commit']
        assert review['backend_commit'] == passed['commit'] and review['database'] == passed['database']
        assert all(review[key] for key in ('tariff_form', 'native_centers', 'harvest_menu', 'native_context', 'no_sample_data'))
        if manifest['version'] == '0.0.4':
            validate_static_copy(manifest, args.environment, stage.name, passed)
            assert all(review[key] for key in ('company_selector', 'authorized_companies_only', 'company_round_trip', 'pending_preserved', 'mobile_layout'))
        if manifest['version'] == '0.0.7':
            validate_android_review(manifest, args.environment, stage.name, passed, review)
        if manifest['version'] == '0.0.8':
            validate_operations_review(manifest, args.environment, stage.name, passed, review)
            operations = stage/'harvest-operations-smoke.json'
            crew = stage/'harvest-crew-smoke.json'
            validate_operations_smokes(manifest, passed, json.loads(operations.read_text()), json.loads(crew.read_text()))
            assert review['operations_smoke_sha256'] == sha(operations)
            assert review['crew_smoke_sha256'] == sha(crew)
        if manifest['version'] == '0.0.5':
            assert re.fullmatch(r'management_'+args.environment+r'_t233_[a-f0-9]{8}', stage.name)
            assert all(review[key] for key in ('plot_selector', 'plots_filtered_by_center',
                                              'plot_selection_reset', 'mobile_layout'))
            assert review['backend_sha256'] == passed['release_sha256']
        if manifest['version'] == '0.0.6':
            assert re.fullmatch(r'management_'+args.environment+r'_(t234|t235)_[a-f0-9]{8}', stage.name)
            assert review['backend_sha256'] == passed['release_sha256']
            assert all(review[key] for key in ('plot_selector', 'plots_filtered_by_center',
                'plot_selection_reset', 'plot_all_location_modes', 'mobile_layout',
                'harvest_dashboard_filters', 'harvest_dashboard_table', 'harvest_dashboard_settings'))
            if '_t235_' in stage.name:
                assert all(review[key] for key in ('harvest_dashboard_workforce',
                    'harvest_costing_form', 'harvest_costing_native_flow'))
                assert args.environment != 'qa-cerro' or review['harvest_costing_reported_case']
        if manifest['version'] in ('0.0.4', '0.0.5', '0.0.6', '0.0.8') and args.environment != 'development':
            assert validate(Path('/var/www/steps-harvest-releases/development')/manifest['commit']) == manifest
            public_hashes(HOSTS['development'], manifest)
        assert re.fullmatch('[a-f0-9]{64}', args.expected_js_sha256 or ''), 'Require the observed static baseline'
        previous_js = current_javascript_hash(HOSTS[args.environment])
        assert previous_js == args.expected_js_sha256, 'Concurrent Harvest build changed; integrate it before publication'
        config = configparser.ConfigParser(interpolation=None)
        config.read(target['config'])
        if passed.get('readonly_copy'):
            assert sha(Path(target['config'])) == json.loads((stage/'baseline.json').read_text())['config_sha256'], 'Backend configuration changed after copy certification'
        backend = Path('/opt/steps-managed/releases')/args.environment/passed['commit']
        assert config['options']['addons_path'].split(',')[0] == str(backend)
        release = json.loads((backend/'release.json').read_text())
        assert release['commit'] == passed['commit']
        for name, expected in release['files'].items():
            assert sha(backend/name) == expected
        root = Path('/var/www/steps-harvest-releases')/args.environment/manifest['commit']
        root.parent.mkdir(parents=True, exist_ok=True)
        if not root.exists():
            shutil.copytree(web, root)
            for path in [root, *root.rglob('*')]:
                os.chmod(path, 0o755 if path.is_dir() else 0o644)
        assert validate(root) == manifest
        config_path = Path(CONFIGS[args.environment]).resolve()
        original = config_path.read_text()
        replacement = patch_config(original, HOSTS[args.environment], root/'app')
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup = Path('/opt/steps_backups')/('harvest-web-'+args.environment+'-'+stamp)
        backup.mkdir(mode=0o700)
        shutil.copy2(config_path, backup/'nginx.conf')
        old_roots = set(re.findall(r'alias\s+(/var/www/[^;]*cosecha)/', original))
        old_roots.update(re.findall(r'alias\s+(/var/www/steps-harvest-releases/'+re.escape(args.environment)+r'/[a-f0-9]{40}/app)/', original))
        for old in old_roots:
            old_release = Path(old).parent/'release.json'
            if old_release.is_file():
                previous = json.loads(old_release.read_text())
                assert previous['repository'] == manifest['repository']
                assert tuple(map(int, manifest['version'].split('.'))) >= tuple(map(int, previous['version'].split('.'))), 'Harvest downgrade refused'
        with tarfile.open(backup/'previous-static.tar.gz', 'w:gz') as archive:
            for old in sorted(old_roots):
                assert Path(old).is_dir() and not Path(old).is_symlink()
                archive.add(old, arcname=old.lstrip('/'))
        assert config_path.read_text() == original
        config_path.write_text(replacement)
        try:
            subprocess.run(['nginx', '-t'], check=True)
            subprocess.run(['systemctl', 'reload', 'nginx'], check=True)
            served = public_hashes(HOSTS[args.environment], manifest, attempts=20)
        except BaseException:
            config_path.write_text(original)
            subprocess.run(['nginx', '-t'], check=True)
            subprocess.run(['systemctl', 'reload', 'nginx'], check=True)
            raise
        receipt = {'environment': args.environment, 'web_commit': manifest['commit'],
            'previous_js_sha256': previous_js,
            'backend_commit': passed['commit'], 'root': str(root), 'served': served,
            'nginx_before_sha256': sha(backup/'nginx.conf'), 'nginx_after_sha256': sha(config_path),
            'backup': str(backup)}
        (backup/'deployment.json').write_text(json.dumps(receipt, indent=2))
        (stage/'harvest-web-deployed.json').write_text(json.dumps(receipt, indent=2))
        print('HARVEST_WEB_PUBLISHED '+json.dumps(receipt))


if __name__ == '__main__':
    main()
