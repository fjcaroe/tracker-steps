"""Rebuild the source archives qualified on restored Cerro Community copies."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import tarfile
import tempfile

from derive_cerro_freight_directory import derive as freight
from derive_cerro_estimation_profile import derive as estimates
from derive_cerro_packing_profile import derive as packing


def write_module(tar, root, required_digest, lf_paths, binary_suffixes):
    digest = hashlib.sha256()
    files = 0
    for file in sorted(root.rglob('*'), key=lambda p: tuple(p.relative_to(root).parts)):
        if not file.is_file() or '__pycache__' in file.parts or file.suffix == '.pyc':
            continue
        name = file.relative_to(root).as_posix()
        raw = file.read_bytes()
        # The accepted archives contain both Linux and Windows checkouts.
        if file.suffix not in binary_suffixes:
            raw = raw.replace(b'\r\n', b'\n')
            if name not in lf_paths:
                raw = raw.replace(b'\n', b'\r\n')
        encoded = name.encode()
        digest.update(len(encoded).to_bytes(4, 'big') + encoded + hashlib.sha256(raw).digest())
        info = tarfile.TarInfo(root.name + '/' + name)
        info.mode = 0o644
        info.size = len(raw)
        tar.addfile(info, io.BytesIO(raw))
        files += 1
    if digest.hexdigest() != required_digest:
        raise ValueError('Source mismatch for the accepted Cerro module ' + root.name)
    return files


def build(source, output, profile='172'):
    if profile not in ('172', 'budget', 'freight', 'contacts', 'contracts', 'concepts', 'picking', 'pack_reports'):
        raise ValueError('Unknown Cerro archive profile')
    receipt = Path(__file__).with_name('cerro_studio_' + profile + '_receipt.json')
    expected = json.loads(receipt.read_text(encoding='utf8'))
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        sources = [source]
        if profile == '172':
            estimates(source / 'step_management_costs', source / 'step_management_estimation_entry', work / 'estimates')
            packing(source, work / 'packing')
            sources = [work / 'estimates', work / 'packing', source]
        elif profile == 'freight':
            freight(source, work / 'freight/step_operations_ui')
            sources = [work / 'freight']
        archive = work / 'profile.tar'
        files = 0
        with tarfile.open(archive, 'w', format=tarfile.PAX_FORMAT) as tar:
            for module, digest in sorted(expected['module_trees'].items()):
                root = next(p / module for p in sources if (p / module / '__manifest__.py').is_file())
                files += write_module(tar, root, digest, expected['lf_source_files'].get(module, ()),
                                      expected.get('binary_suffixes', ['.png']))
        result = hashlib.sha256(archive.read_bytes()).hexdigest()
        if result != expected['archive_sha256'] or files != expected.get('files', files):
            raise ValueError('The rebuilt archive differs from the qualified Cerro candidate')
        with output.open('xb') as target, archive.open('rb') as incoming:
            shutil.copyfileobj(incoming, target)
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--profile', choices=('172', 'budget', 'freight', 'contacts', 'contracts', 'concepts', 'picking', 'pack_reports'), default='172')
    args = parser.parse_args()
    print(build(args.source, args.output, args.profile))
