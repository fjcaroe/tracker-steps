"""Build the pinned original contract-review module for the free payroll dependency."""
import argparse
import ast
import hashlib
import json
from pathlib import Path

from build_numeric_input_engine import hashes, require, seal
from original_history_engine_contract import _snapshot


MODULE = 'step_payroll_engine_transition'
MANIFEST_SHA = '8fac371cb159bc8eb9d21a7b4e1de5aedc988bfa219768f0719a77a78eaeb228'
CERRO_MANIFEST_SHA = '39256e618e21aa04b2607ce01881c8283f88814a59b26fa3a9aaaec4e62ce706'
CERRO_SOURCE = 'b10cfb4bc4c3ebb3c061b99b0d7905bf6e2e307f357721a96f77c2174f600e24'


def build(source, output, expected, product='sys'):
    require(product in ('sys', 'cerro'), 'Unknown original contract-review product')
    original = _snapshot(source)
    before = seal(hashes(original))
    require(before == expected, 'Unreviewed contract-review source')
    if product == 'cerro':
        require(before == CERRO_SOURCE, 'Unexpected original Cerro contract-review source')
    manifest = original['__manifest__.py']
    manifest_sha = CERRO_MANIFEST_SHA if product == 'cerro' else MANIFEST_SHA
    version = '18.0.1.0.0' if product == 'cerro' else '18.0.1.2.0'
    require(hashlib.sha256(manifest).hexdigest() == manifest_sha, 'Unexpected original contract-review manifest')
    values = ast.literal_eval(manifest.decode())
    require((values['version'], values['license'], values['depends']) == (version, 'LGPL-3', ['hr_payroll']),
            'Unexpected original contract-review dependency')
    old = b"'depends': ['hr_payroll']"
    require(manifest.count(old) == 1, 'Ambiguous native payroll dependency')
    # Keep the historical contract-review message ahead of the Community
    # structural admission. A pending review takes precedence in native SyS.
    new = b"'depends': ['payroll', 'step_simpledigital_oca_security']"
    files = {**original, '__manifest__.py': manifest.replace(old, new)}
    output.mkdir(parents=True, exist_ok=False)
    for name, data in files.items():
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    require(_snapshot(output) == files, 'Derived contract-review files changed')
    return {'module': MODULE, 'files': len(files), 'original': before, 'derived': seal(hashes(files))}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--expected', required=True)
    parser.add_argument('--product', choices=('sys', 'cerro'), default='sys')
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output, args.expected, args.product), sort_keys=True))
