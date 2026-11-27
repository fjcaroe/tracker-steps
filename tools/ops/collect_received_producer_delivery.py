"""Collect T246 certification and deployment evidence, without credentials or database dumps."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('release_root', type=Path)
args = parser.parse_args()
base = args.release_root.resolve()
assert base.parent == Path('/opt/steps-validation') and base.name.startswith('t246-release-')
release = base / 'release.tar.gz'
with tarfile.open(release) as archive:
    proof = json.load(archive.extractfile('release.json'))
assert proof['versions'] == {'step_packing_producer_change': '18.0.1.1.0'}
sha = hashlib.sha256(release.read_bytes()).hexdigest()
output = base / 'delivery'
assert not output.is_symlink()
output.mkdir(mode=0o700, exist_ok=True)
(output / 'release.json').write_text(json.dumps(proof, indent=2))
registry = json.loads(Path(__file__).with_name('environments.json').read_text())
results = {}
for target in ('development', 'cerro', 'qa-cerro'):
    stage = base.parent / ('management_' + target + '_t246_' + proof['commit'][:8])
    passed = json.loads((stage / 'qa_passed.json').read_text())
    assert passed['commit'] == proof['commit'] and passed['release_sha256'] == sha and passed['business_preserved']
    backups = []
    for candidate in Path('/opt/steps_backups').glob('management_' + target + '_*/deployment.json'):
        deployment = json.loads(candidate.read_text())
        if deployment['commit'] == proof['commit'] and deployment['sha256'] == sha:
            backups.append(candidate)
    assert len(backups) == 1
    files = {'qa.json': stage / 'qa_passed.json', 'qa.log': Path(passed['log']),
        'deployment.json': backups[0],
        'live-verification.log': stage / ('verify-' + registry['environments'][target]['database'] + '.log'),
        'existing-business-flow.log': stage / 'existing-business-flow.log'}
    for suffix, source in files.items():
        assert source.is_file()
        shutil.copyfile(source, output / (target + '-' + suffix))
    results[target] = {'backup': str(backups[0].parent), 'copy': passed['database'], 'stage': str(stage)}
for filename in ('pair.json', 'isolation.log'):
    shutil.copyfile(base / filename, output / filename)
helpers = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in (
    'manage_management.py', 'verify_producer_change.py', 'run_received_producer_business.py', 'verify_received_producer_business.py')}
(output / 'operations.json').write_text(json.dumps({'commit': proof['commit'], 'sha256': sha,
    'environments': results, 'helpers': helpers}, indent=2))
print('T246_EVIDENCE_COLLECTED ' + str(output))
