"""Read-only byte comparison of deployed addon files against the release archive."""
import argparse
import hashlib
from pathlib import Path, PurePosixPath
import tarfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('archive')
parser.add_argument('target')
args = parser.parse_args()
checked = 0
with tarfile.open(args.archive, 'r:gz') as archive:
    for item in archive.getmembers():
        if not item.isfile():
            continue
        relative = PurePosixPath(item.name)
        if relative.is_absolute() or '..' in relative.parts or relative.parts[0] not in {'step_support_assistant', 'step_support_assistant_knowledge'}:
            raise RuntimeError('Unexpected release path')
        actual = Path(args.target).joinpath(*relative.parts)
        expected = archive.extractfile(item).read()
        if not actual.is_file() or hashlib.sha256(actual.read_bytes()).digest() != hashlib.sha256(expected).digest():
            raise RuntimeError('Release mismatch: ' + item.name)
        checked += 1
print(f'ASSISTANT_RELEASE_VERIFIED files={checked} target={args.target}')
