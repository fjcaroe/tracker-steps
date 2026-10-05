"""Verify every agricultural release file against a reviewed Git commit."""
import argparse
import hashlib
from pathlib import Path
import subprocess
import tarfile

MODULES = {'step_export', 'step_producers', 'step_producer_fruit_flow',
           'step_inventory_packing', 'step_packing_operations'}
TEXT = {'.py', '.xml', '.csv', '.js', '.scss', '.css', '.svg', '.webmanifest', '.md'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('commit')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    commit = subprocess.check_output(['git', 'rev-parse', args.commit + '^{commit}'], cwd=root, text=True).strip()
    seen = set()
    with tarfile.open(args.archive, 'r:gz') as archive:
        for member in archive.getmembers():
            path = Path(member.name)
            assert member.isfile() and not path.is_absolute() and '..' not in path.parts
            assert path.parts and path.parts[0] in MODULES and member.name not in seen
            seen.add(member.name)
            expected = subprocess.check_output(['git', 'show', commit + ':' + member.name], cwd=root)
            actual = archive.extractfile(member).read()
            if path.suffix in TEXT:
                expected, actual = expected.replace(b'\r\n', b'\n'), actual.replace(b'\r\n', b'\n')
            assert actual == expected, 'Release differs from Git: ' + member.name
    assert seen, 'Empty release'
    print('RELEASE_COMMIT_OK commit=' + commit + ' files=' + str(len(seen)))
    print('SHA256=' + hashlib.sha256(args.archive.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
