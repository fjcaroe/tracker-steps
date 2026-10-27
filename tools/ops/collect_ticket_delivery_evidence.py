"""Collect private proofs and repeat read-only native verification before closure.

Specification contains committed package identities and the three exact run IDs.
Does not deploy, refresh databases, send messages, or read backup credentials.
"""
import argparse
from contextlib import redirect_stdout
import fcntl
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert os.geteuid() == 0
    repository = Path(__file__).resolve().parents[2]
    assert not (repository / '.git').exists() or not args.output.resolve().is_relative_to(repository)
    spec = json.loads(args.spec.read_text())
    targets = ('development', 'cerro', 'qa-cerro')
    args.output.mkdir(parents=True, exist_ok=False, mode=0o700)
    with open('/run/lock/steps-environments.lock', 'a') as lease:
        print('EVIDENCE_WAITING_FOR_SHARED_LEASE', flush=True)
        fcntl.flock(lease, fcntl.LOCK_EX)
        for group, entry in spec.items():
            assert re.fullmatch('[a-z0-9_-]+', group)
            assert set(entry['runs']) == set(targets)
            root = Path(entry['root']).resolve()
            assert root.is_relative_to('/opt/steps-validation')
            release = root / entry['release']
            assert hashlib.sha256(release.read_bytes()).hexdigest() == entry['sha256']
            output = args.output / group; output.mkdir()
            reviewed = {str(ticket): {'commit': entry['commit'], 'sha256': entry['sha256'],
                                      'reviewed_message_id': ident} for ticket, ident in entry['reviewed'].items()}
            (output / 'delivery-reviewed.json').write_text(json.dumps(reviewed, indent=2))
            for target in targets:
                run_id = entry['runs'][target]
                assert re.fullmatch('[a-z0-9_]{1,24}', run_id)
                stage = Path('/opt/steps-validation') / ('management_' + target + '_' + run_id)
                proof = json.loads((stage / 'qa_passed.json').read_text())
                assert (proof['commit'], proof['release_sha256']) == (entry['commit'], entry['sha256'])
                log = Path(proof['log']).resolve()
                assert log.is_relative_to(stage.resolve())
                shutil.copyfile(stage / 'qa_passed.json', output / (target + '-qa.json'))
                shutil.copyfile(log, output / (target + '-qa.log'))
                shutil.copyfile(stage / ('verify-' + proof['database'] + '.log'), output / (target + '-clone-flow.log'))
                if entry['kind'] == 'packaging-master':
                    matches = list(stage.glob('material-hierarchy-*.log'))
                    assert len(matches) == 1 or target == 'cerro'
                    # A live configuration receipt is stronger when present.
                    db = {'development': 'LAB_TAREAS', 'cerro': 'CERRO_EL_PLOMO', 'qa-cerro': 'QA-CERROELPLOMO'}[target]
                    live = stage / ('material-hierarchy-' + db + '.log')
                    shutil.copyfile(live if live.exists() else matches[0], output / (target + '-hierarchy.log'))
                receipts = []
                for backup in Path('/opt/steps_backups').glob('management_' + target + '_*'):
                    receipt = backup / 'deployment.json'
                    if receipt.exists():
                        value = json.loads(receipt.read_text())
                        if value.get('commit') == entry['commit'] and value.get('sha256') == entry['sha256']:
                            receipts.append(receipt)
                assert len(receipts) == 1, ('Ambiguous deployment receipt', group, target)
                shutil.copyfile(receipts[0], output / (target + '-deployment.json'))
                result = subprocess.run(['python3', str(root / 'tools/ops/manage_management.py'),
                    'verify', target, str(release), run_id, '--kind', entry['kind']], text=True, capture_output=True)
                (output / (target + '-live.log')).write_text(result.stdout + result.stderr)
                assert result.returncode == 0 and 'MANAGEMENT_VERIFY_OK' in result.stdout, result.stderr[-2000:]
                print('NATIVE_DELIVERY_REVERIFIED', group, target, flush=True)
        # Invoke only the existing read-only verifier while retaining this lease.
        tool = Path(next(iter(spec.values()))['root']) / 'tools/ops/provision_cerro_qa.py'
        module_spec = importlib.util.spec_from_file_location('customer_qa_final_verifier', tool)
        module = importlib.util.module_from_spec(module_spec); module_spec.loader.exec_module(module)
        capture = io.StringIO()
        # The verifier's child stdout must also be preserved as evidence.
        with (args.output / 'qa-final-isolation.log').open('w') as stream:
            with redirect_stdout(capture):
                original_run = module.run
                def audited_run(*command, **kwargs):
                    if kwargs.get('capture_output'):
                        return original_run(*command, **kwargs)
                    result = subprocess.run(command, check=True, text=True, capture_output=True)
                    print(result.stdout, end='')
                    return result
                module.run = audited_run
                module.verify()
            stream.write(capture.getvalue())
        for group in spec:
            shutil.copyfile(args.output / 'qa-final-isolation.log', args.output / group / 'qa-final-isolation.log')
    with tarfile.open(str(args.output) + '.tar', 'w') as archive:
        for file in sorted(args.output.rglob('*')):
            if file.is_file(): archive.add(file, arcname=file.relative_to(args.output))
    print('TICKET_DELIVERY_EVIDENCE_COLLECTED ' + str(args.output) + '.tar', flush=True)


if __name__ == '__main__':
    main()
