"""Promote the certified T244/T245 package through the canonical publishers."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from harvest_web_policy import validate_operations_review, validate_operations_smokes


def read(path):
    return json.loads(path.read_text())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('base', type=Path)
    p.add_argument('--apply', action='store_true')
    a = p.parse_args()
    assert a.base.resolve() == a.base and a.base.parent == Path('/opt/steps-validation')
    release = read(a.base / 'backend-release.json')
    web = a.base / 'web'
    frontend = read(web / 'release.json')
    assert frontend['version'] == '0.0.12'
    assert release['versions'] == {'step_harvest_launcher': '18.0.1.7.0', 'step_cosecha_operations': '18.0.1.2.0'}
    package = a.base / 'harvest-odoo.tar.gz'
    sha = hashlib.sha256(package.read_bytes()).hexdigest()
    run = 't244245_' + release['commit'][:8]
    environments = ('development', 'qa-cerro', 'cerro')
    for environment in environments:
        stage = a.base.parent / ('management_' + environment + '_' + run)
        qa = read(stage / 'qa_passed.json')
        assert qa['commit'] == release['commit'] and qa['release_sha256'] == sha
        validate_operations_review(frontend, environment, stage.name, qa, read(stage / 'harvest-browser-proof.json'))
        validate_operations_smokes(frontend, qa, read(stage / 'harvest-operations-smoke.json'), read(stage / 'harvest-crew-smoke.json'))
    tests = read(a.base / 'frontend-tests.json')
    assert tests['web_commit'] == frontend['commit'] and tests['passed'] >= 72
    assert tests['log_sha256'] == hashlib.sha256((a.base / 'frontend-tests.log').read_bytes()).hexdigest()
    print('HARVEST_HOURS_PROMOTION_PREFLIGHT_OK targets=3 version=0.0.12', flush=True)
    if not a.apply:
        return
    tools = Path(__file__).resolve().parent
    baselines = read(a.base / 'static-before.json')
    for environment in environments:
        stage = a.base.parent / ('management_' + environment + '_' + run)
        log = a.base / ('deploy-' + environment + '.log')
        assert not log.exists(), 'Inspect the previous deployment receipt before resuming'
        print('HARVEST_HOURS_PROMOTION_BEGIN ' + environment, flush=True)
        with log.open('x') as output:
            subprocess.run([sys.executable, str(tools / 'manage_management.py'), 'deploy', environment,
                str(package), run, '--kind', 'harvest-app'], stdout=output, stderr=subprocess.STDOUT, check=True)
        with (a.base / ('publish-' + environment + '.log')).open('x') as output:
            subprocess.run([sys.executable, str(tools / 'publish_harvest_web.py'), 'deploy', environment,
                '--web', str(web), '--stage', str(stage), '--expected-js-sha256', baselines[environment]],
                stdout=output, stderr=subprocess.STDOUT, check=True)
        print('HARVEST_HOURS_PROMOTION_OK ' + environment, flush=True)


if __name__ == '__main__':
    main()
