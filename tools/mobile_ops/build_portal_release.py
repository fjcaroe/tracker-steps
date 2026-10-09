"""Create an immutable portal-only package from a committed Git ref."""
import argparse
import ast
import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

MODULES = ('step_mobile_portal', 'step_mobile_portal_colaciones', 'step_mobile_portal_mobilization', 'step_mobile_portal_tracker')
root = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('output', type=Path)
p.add_argument('--ref', default='HEAD')
args = p.parse_args()
commit = subprocess.check_output(['git', 'rev-parse', args.ref], cwd=root, text=True).strip()
data = subprocess.check_output(['git', 'archive', commit, *MODULES], cwd=root)
proof = {'commit': commit, 'versions': {}, 'files': {}}
with tarfile.open(fileobj=io.BytesIO(data)) as source:
    for item in source.getmembers():
        if not item.isfile():
            continue
        content = source.extractfile(item).read()
        proof['files'][item.name] = hashlib.sha256(content).hexdigest()
        if item.name.endswith('/__manifest__.py'):
            proof['versions'][item.name.split('/')[0]] = ast.literal_eval(content.decode())['version']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(args.output, 'w:gz') as target:
        for item in source.getmembers():
            if item.isfile():
                target.addfile(item, source.extractfile(item))
        content = json.dumps(proof, sort_keys=True).encode()
        item = tarfile.TarInfo('release.json'); item.size = len(content)
        target.addfile(item, io.BytesIO(content))
print(json.dumps({'commit': commit, 'versions': proof['versions'], 'archive_sha256': hashlib.sha256(args.output.read_bytes()).hexdigest()}))
