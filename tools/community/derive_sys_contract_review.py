"""Build the SyS original contract-review module for the free payroll dependency."""
import argparse
import ast
import hashlib
import json
from pathlib import Path

from build_numeric_input_engine import hashes, require, seal
from original_history_engine_contract import _snapshot


MODULE = 'step_payroll_engine_transition'
MANIFEST_SHA = '8fac371cb159bc8eb9d21a7b4e1de5aedc988bfa219768f0719a77a78eaeb228'


def build(source, output, expected):
    original = _snapshot(source)
    before = seal(hashes(original))
    require(before == expected, 'Unreviewed SyS contract-review source')
    manifest = original['__manifest__.py']
    require(hashlib.sha256(manifest).hexdigest() == MANIFEST_SHA, 'Unexpected SyS contract-review manifest')
    values = ast.literal_eval(manifest.decode())
    require((values['version'], values['license'], values['depends']) == ('18.0.1.2.0', 'LGPL-3', ['hr_payroll']),
            'Unexpected SyS contract-review dependency')
    old = b"'depends': ['hr_payroll']"
    require(manifest.count(old) == 1, 'Ambiguous native payroll dependency')
    files = {**original, '__manifest__.py': manifest.replace(old, b"'depends': ['payroll']")}
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
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output, args.expected), sort_keys=True))
