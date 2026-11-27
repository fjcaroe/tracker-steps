"""Reproduce the free source overlay used on the licensed native Cerro control."""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import shutil
import tarfile
import tempfile

RECEIPT = Path(__file__).with_name('cerro_native_providers_receipt.json')


def seal(base, output):
    receipt = json.loads(RECEIPT.read_text(encoding='utf8'))
    roots = [base / name for name in receipt['roots']]
    with tempfile.TemporaryFile() as data:
        with tarfile.open(fileobj=data, mode='w', format=tarfile.PAX_FORMAT) as archive:
            for name, expected in sorted(receipt['installed_overlay_modules'].items()):
                index, directory = next((i, root / name) for i, root in enumerate(roots)
                                        if (root / name / '__manifest__.py').is_file())
                manifest = ast.literal_eval((directory / '__manifest__.py').read_text(encoding='utf8'))
                if (index, manifest['license'], manifest['version']) != (expected['root_index'], expected['license'], expected['version']):
                    raise ValueError('Different source for ' + name)
                digest = hashlib.sha256()
                for file in sorted(directory.rglob('*'), key=lambda p: tuple(p.relative_to(directory).parts)):
                    if not file.is_file() or '__pycache__' in file.parts or file.suffix == '.pyc':
                        continue
                    member = file.relative_to(directory).as_posix()
                    raw = file.read_bytes()
                    encoded = member.encode()
                    digest.update(len(encoded).to_bytes(4, 'big') + encoded + hashlib.sha256(raw).digest())
                    info = tarfile.TarInfo(name + '/' + member)
                    info.mode = 0o644
                    info.size = len(raw)
                    archive.addfile(info, io.BytesIO(raw))
                if digest.hexdigest() != expected['sha256']:
                    raise ValueError('Source bytes changed for ' + name)
        data.seek(0)
        sha = hashlib.sha256(data.read()).hexdigest()
        if sha != receipt['archive_sha256']:
            raise ValueError('The rebuilt archive differs from the qualified native overlay')
        data.seek(0)
        with output.open('xb') as target:
            shutil.copyfileobj(data, target)
    return sha


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validation-root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(seal(args.validation_root, args.output))
