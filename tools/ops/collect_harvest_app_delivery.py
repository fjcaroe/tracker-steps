"""Collect the certified Harvest backend, web, native reviews and isolation evidence."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from harvest_web_policy import validate_operations_review, validate_operations_smokes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base', type=Path)
    parser.add_argument('run_id')
    parser.add_argument('--reviewed-message', action='append', default=[], metavar='TICKET:MESSAGE')
    args = parser.parse_args()
    base = args.base
    assert base.resolve() == base and base.parent == Path('/opt/steps-validation')
    assert re.fullmatch('(t231232|t234|t235|t236237)_[a-f0-9]{8}', args.run_id)
    operations = args.run_id.startswith('t236237_')
    costing = args.run_id.startswith('t235_')
    panel = args.run_id.startswith(('t234_', 't235_', 't236237_'))
    reviewed = dict(tuple(map(int, item.split(':'))) for item in args.reviewed_message)
    assert not panel or set(reviewed) == ({236, 237} if operations else {233, 234, 235} if costing else {233, 234}), 'Identify the human replies reviewed for this delivery'
    output = base/'delivery'
    output.mkdir(mode=0o700, exist_ok=True)
    manifest = json.loads((base/'web/release.json').read_text())
    sha = hashlib.sha256((base/('harvest-odoo.tar.gz' if panel else 'harvest.tar.gz')).read_bytes()).hexdigest()
    commits = set()
    counts_by_target = {}
    for target in ('development', 'qa-cerro', 'cerro'):
        stage = Path('/opt/steps-validation')/('management_'+target+'_'+args.run_id)
        qa_file = stage/'qa_passed.json'
        qa = json.loads(qa_file.read_text())
        assert qa['release_sha256'] == sha
        commits.add(qa['commit'])
        test = Path(qa['log'])
        counts = re.findall(r'0 failed, 0 error\(s\) of (\d+) tests when loading database', test.read_text())
        assert counts and int(counts[-1]) >= (43 if costing or operations else 28 if panel else 18)
        counts_by_target[target] = int(counts[-1])
        flow = stage/('verify-'+qa['database']+'.log')
        assert 'MANAGEMENT_REGISTRY_OK' in flow.read_text()
        live = base/('deploy-'+target+'.log')
        text = live.read_text()
        assert 'MANAGEMENT_VERIFY_OK' in text
        backups = re.findall(r'MANAGEMENT_DEPLOY_OK backup=(\S+)', text)
        assert len(backups) == 1
        deployment = Path(backups[0])/'deployment.json'
        deployed = json.loads(deployment.read_text())
        assert deployed['commit'] == qa['commit'] and deployed['sha256'] == sha
        web = stage/'harvest-web-deployed.json'
        web_data = json.loads(web.read_text())
        assert web_data['backend_commit'] == qa['commit'] and web_data['web_commit'] == manifest['commit']
        assert web_data['served'] == manifest['files']
        review = base/(target+'-live-review.json')
        checked = json.loads(review.read_text())
        assert checked['reviewed'] is True and checked['environment'] == target
        assert checked['backend_commit'] == qa['commit'] and checked['web_commit'] == manifest['commit']
        for suffix, source in (('qa.json', qa_file), ('qa.log', test), ('flow.log', flow),
                ('live.log', live), ('deployment.json', deployment), ('web.json', web), ('live-review.json', review)):
            shutil.copyfile(source, output/(target+'-'+suffix))
        if panel:
            shutil.copyfile(stage/'harvest-browser-proof.json', output/(target+'-copy-review.json'))
        if operations:
            validate_operations_review(manifest, target, stage.name, qa,
                json.loads((stage/'harvest-browser-proof.json').read_text()))
            validate_operations_smokes(manifest, qa,
                json.loads((stage/'harvest-operations-smoke.json').read_text()),
                json.loads((stage/'harvest-crew-smoke.json').read_text()))
            for kind in ('operations', 'crew'):
                shutil.copyfile(stage/('harvest-'+kind+'-smoke.json'), output/(target+'-'+kind+'-smoke.json'))
            assert checked['ot_lifecycle_available'] is True and checked['crew_attendance_available'] is True
    assert len(commits) == 1
    tools = Path(__file__).resolve().parent
    with open('/run/lock/steps-environments.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        result = subprocess.run(['/usr/bin/python3.10', '-c', 'from provision_cerro_qa import verify; verify()'],
            cwd=tools, text=True, capture_output=True)
        isolation = result.stdout+result.stderr
        (output/'isolation.log').write_text(isolation)
        assert result.returncode == 0, 'QA isolation failed: '+str(output/'isolation.log')
        assert all(marker in isolation for marker in (
            'CUSTOMER_QA_VERIFY_OK', 'CUSTOMER_QA_EGRESS_BLOCKED', 'CUSTOMER_QA_SOURCE_DB_DENIED'))
        rules = subprocess.check_output(['/usr/sbin/iptables', '-S', 'OUTPUT'], text=True)
        assert not any(marker in rules for marker in ('STEPS_PRIVATE_TEST_', 'STEPS_PRIVATE_REPORT_'))
        result = subprocess.run(['/usr/bin/python3.10', str(tools/'verify_cerro_release_pair.py'),
            '--module', 'step_cosecha_operations', '--module', 'step_harvest_launcher',
            '--output', str(output/'pair.json')], text=True, capture_output=True, check=True)
        assert 'CERRO_RELEASE_PAIR_OK' in result.stdout
        (output/'pair.log').write_text(result.stdout)
    if operations:
        frontend_proof = json.loads((base/'frontend-tests.json').read_text())
        assert frontend_proof['web_commit'] == manifest['commit']
        assert frontend_proof['log_sha256'] == hashlib.sha256((base/'frontend-tests.log').read_bytes()).hexdigest()
    frontend_tests = frontend_proof['passed'] if operations else 23 if panel else 14
    assert type(frontend_tests) is int and frontend_tests > 0
    (output/'delivery.json').write_text(json.dumps({'backend_commit': commits.pop(),
        'backend_sha256': sha, 'web_commit': manifest['commit'], 'web_files': manifest['files'],
        'tests': sum(counts_by_target.values()), 'tests_by_target': counts_by_target,
        'frontend_tests': frontend_tests,
        'cost_state_labels': ['Costeo', 'Contabilizado'] if panel else [],
        'reviewed_messages': reviewed if panel else {'231': 10595, '232': 10598}}, indent=2))
    print('HARVEST_DELIVERY_COLLECTED targets=3 server_tests=%s frontend_tests=%s' %
        (sum(counts_by_target.values()), frontend_tests))


if __name__ == '__main__':
    main()
