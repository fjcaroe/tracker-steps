"""Collect private T171 review-1 publication and isolation evidence."""
import argparse
import fcntl
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--console-dir', type=Path, required=True)
    parser.add_argument('--pdf-review', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert re.fullmatch('[a-z0-9_]{1,24}', args.run_id)
    assert args.console_dir.resolve().is_relative_to('/opt/steps-validation')
    assert args.output.resolve().is_relative_to('/opt/steps-validation')
    args.output.mkdir(parents=True, exist_ok=False, mode=0o700)
    identities = set()
    for target in ('development', 'cerro', 'qa-cerro'):
        stage = Path('/opt/steps-validation') / ('management_' + target + '_' + args.run_id)
        proof = json.loads((stage / 'qa_passed.json').read_text())
        live = args.console_dir / ('deploy-' + target + '.log')
        assert 'MANAGEMENT_VERIFY_OK' in live.read_text()
        backups = re.findall(r'MANAGEMENT_DEPLOY_OK backup=(\S+)', live.read_text())
        assert len(backups) == 1
        receipt = Path(backups[0]) / 'deployment.json'
        deployment = json.loads(receipt.read_text())
        assert (proof['commit'], proof['release_sha256']) == (deployment['commit'], deployment['sha256'])
        identities.add((proof['commit'], proof['release_sha256']))
        sources = {'qa.json': stage / 'qa_passed.json', 'qa.log': Path(proof['log']),
                   'verify.log': stage / ('verify-' + proof['database'] + '.log'),
                   'live.log': live, 'deployment.json': receipt}
        for suffix, source in sources.items():
            shutil.copyfile(source, args.output / (target + '-' + suffix))
        if target == 'cerro':
            shutil.copyfile(stage / 'policy-refresh-CERRO_EL_PLOMO.log', args.output / 'cerro-refresh.log')
            shutil.copyfile(stage / 't171-review-proforma.pdf', args.output / 't171-review-proforma.pdf')
    assert len(identities) == 1
    shutil.copyfile(args.pdf_review, args.output / 'pdf-review.json')
    with open('/run/lock/steps-environments.lock', 'a') as lease:
        print('T171_WAITING_FINAL_ISOLATION_LEASE', flush=True)
        fcntl.flock(lease, fcntl.LOCK_EX)
        result = subprocess.run(['/usr/bin/python3.10', '-c', 'from provision_cerro_qa import verify; verify()'],
            cwd=Path(__file__).resolve().parent, capture_output=True, text=True, check=True)
        text = result.stdout + result.stderr
        assert all(marker in text for marker in (
            'CUSTOMER_QA_VERIFY_OK', 'CUSTOMER_QA_EGRESS_BLOCKED', 'CUSTOMER_QA_SOURCE_DB_DENIED'))
        assert 'STEPS_PRIVATE_REPORT_' not in subprocess.check_output(['/usr/sbin/iptables', '-S', 'OUTPUT'], text=True)
        (args.output / 'isolation.log').write_text(text)
        result = subprocess.run(['/usr/bin/python3.10', str(Path(__file__).with_name('verify_cerro_release_pair.py')),
            '--module', 'step_packing_fruit_proforma', '--output', str(args.output / 'pair.json')],
            capture_output=True, text=True, check=True)
        assert 'CERRO_RELEASE_PAIR_OK' in result.stdout
        (args.output / 'pair.log').write_text(result.stdout)
    with tarfile.open(str(args.output) + '.tar', 'w') as archive:
        for file in sorted(args.output.iterdir()):
            assert file.is_file()
            archive.add(file, arcname=file.name)
    Path(str(args.output) + '.tar').chmod(0o600)
    print('T171_POLICY_DELIVERY_COLLECTED tests=90 ' + str(args.output) + '.tar', flush=True)


if __name__ == '__main__':
    main()
