"""Verify with trusted Git code, then seal inert private acceptance evidence.

No database access and no artifact Python execution. The archive is deterministic
and contains an exhaustive manifest; its adjacent receipt binds the outer bytes.
"""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile

from verify_multifront_evidence import verify


def encode(value):
    return json.dumps(value, indent=2, sort_keys=True).encode('utf-8')


def seal(evidence, output, *, quality_extension=False, critical_extension=False, critical_generation='R3'):
    evidence, output = Path(evidence).resolve(), Path(output).resolve()
    repo = Path(__file__).resolve().parents[2]
    assert not output.is_relative_to(repo) and not output.exists()
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip(), 'Commit the trusted verifier first'
    options={'operational_extensions':True}
    if quality_extension:options['quality_extension']=True
    if critical_extension:options['critical_extension']=True
    if critical_generation != 'R3':options['critical_generation']=critical_generation
    summary = verify(evidence, repo=repo, **options)
    files = {}
    for path in evidence.rglob('*'):
        assert not path.is_symlink(), 'Symlink evidence refused'
        if path.is_file():files['acceptance/'+path.relative_to(evidence).as_posix()] = path.read_bytes()
    files['summary.json'] = encode(summary)
    manifest = {'schema':1,'files':{name:hashlib.sha256(body).hexdigest() for name,body in sorted(files.items())},
        'artifact_code_executed':False,'database_accessed':False,'production_changed':False}
    files['seal-manifest.json'] = encode(manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as handle:
        with gzip.GzipFile(fileobj=handle,mode='wb',filename='',mtime=0) as compressed:
            with tarfile.open(fileobj=compressed,mode='w') as archive:
                for name, body in sorted(files.items()):
                    item=tarfile.TarInfo(name);item.mode=0o600;item.size=len(body)
                    archive.addfile(item,io.BytesIO(body))
    receipt = {'schema':1,'file':output.name,'bytes':output.stat().st_size,
        'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'members':len(files),
        'summary_sha256':hashlib.sha256(files['summary.json']).hexdigest(),
        'seal_manifest_sha256':hashlib.sha256(files['seal-manifest.json']).hexdigest(),
        'git_revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
        'seal_tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'artifact_code_executed':False,'database_accessed':False,'production_changed':False}
    receipt_path=output.with_name(output.name+'.receipt.json')
    with os.fdopen(os.open(receipt_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as handle:
        handle.write(encode(receipt))
    return receipt


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--quality-extension',action='store_true')
    parser.add_argument('--critical-extension',action='store_true')
    parser.add_argument('--critical-generation',choices=('R3','S','T','U'),default='R3')
    args=parser.parse_args()
    print(json.dumps(seal(args.evidence,args.output,quality_extension=args.quality_extension,critical_extension=args.critical_extension,critical_generation=args.critical_generation),sort_keys=True))
