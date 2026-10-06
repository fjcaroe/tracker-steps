"""Build an immutable management release directly from committed Git blobs."""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import xml.etree.ElementTree as ET

MODULES = ('step_management_costs', 'step_management_costs_agriculture',
           'step_management_costs_machinery', 'step_management_costs_tracker',
           'step_agriculture_catalogs', 'step_management_costs_producers')
SUFFIXES = {'.py', '.xml', '.csv', '.js', '.scss', '.css', '.svg', '.png', '.jpg', '.md', '.rst'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--commit', default='HEAD')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    assert not args.output.resolve().is_relative_to(root)
    commit = subprocess.check_output(['git', 'rev-parse', args.commit + '^{commit}'], cwd=root, text=True).strip()
    raw = subprocess.check_output(['git', 'archive', '--format=tar', commit, *MODULES], cwd=root)
    entries = {}
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        for member in archive.getmembers():
            if not member.isfile() or Path(member.name).suffix not in SUFFIXES:
                continue
            data = archive.extractfile(member).read()
            if member.name.endswith('.py'):
                ast.parse(data.decode('utf-8'), member.name)
            elif member.name.endswith(('.xml', '.svg')):
                ET.fromstring(data)
            entries[member.name] = data
    versions = {name: ast.literal_eval(entries[name + '/__manifest__.py'].decode())['version'] for name in MODULES}
    proof = {'commit': commit, 'versions': versions, 'files': {name: hashlib.sha256(data).hexdigest() for name, data in entries.items()}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(args.output, 'w:gz') as archive:
        for name, data in [*sorted(entries.items()), ('release.json', json.dumps(proof, indent=2).encode())]:
            member = tarfile.TarInfo(name)
            member.size = len(data)
            member.mode = 0o644
            archive.addfile(member, io.BytesIO(data))
    print('MANAGEMENT_RELEASE_OK ' + json.dumps({'commit': commit, 'sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(), 'files': len(entries), 'versions': versions}))


if __name__ == '__main__':
    main()
