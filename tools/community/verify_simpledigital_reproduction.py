"""Rebuild a private provider derivation and compare every runtime byte."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def files(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--accepted-addons',type=Path,required=True)
    parser.add_argument('--rebuild-root',type=Path,required=True)
    args=parser.parse_args()
    assert str(args.rebuild_root.resolve()).startswith('/opt/steps-validation/')
    assert str(args.accepted_addons.resolve()).startswith('/opt/steps-validation/')
    assert not args.rebuild_root.exists()
    builder=args.accepted_addons/'tools/community/build_simpledigital_candidate.py'
    subprocess.run([sys.executable,str(builder),'--source',str(args.source),
                    '--output',str(args.rebuild_root/'addons')],check=True)
    accepted=files(args.accepted_addons/'l10n_cl_simpledigital_payroll')
    rebuilt=files(args.rebuild_root/'addons/l10n_cl_simpledigital_payroll')
    assert accepted==rebuilt,'Provider differs from reproducible derivation'
    result={'same_runtime_bytes':True,'files':len(accepted),
            'builder_sha256':hashlib.sha256(builder.read_bytes()).hexdigest(),
            'runtime_files_sha256':hashlib.sha256(json.dumps(accepted,sort_keys=True).encode()).hexdigest()}
    (args.rebuild_root/'reproduction.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
