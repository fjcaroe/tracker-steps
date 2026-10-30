"""Stage committed free sources for a private operational migration rehearsal.

Run locally. Uploads only Git-owned addons/tools, never credentials or business
data. The server derives the already audited AGPL provider in its private root.
This does not create/restore a database or publish any active environment.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess

from audit_multifront_installation import OWN_MODULES

EXTENSIONS = ('step_payroll_advantages_oca', 'step_payroll_benefits_native_reference',
              'step_payroll_original_report')
PROVIDER = '/opt/steps-managed/payroll/cerro/2dc161f26c6d549a00c474bf81e8c3f83e984092/l10n_cl_simpledigital_payroll'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--quality-extension',action='store_true')
    args = parser.parse_args()
    assert re.fullmatch('/opt/steps-validation/community-multifront-parallel-[A-Za-z0-9-]+', args.root)
    repo = Path(__file__).resolve().parents[2]
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip(), 'Commit the exact candidate first'
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    quality=('step_quality_contracts','step_quality_oca','step_qa_native_reference') if args.quality_extension else ()
    modules = tuple(dict.fromkeys((*OWN_MODULES, *EXTENSIONS,*quality)))
    body = subprocess.check_output(['git', 'archive', '--format=tar', revision, *modules,
                                    'tools/community', 'tools/ops'], cwd=repo)
    digest = hashlib.sha256(body).hexdigest()
    program = '''import hashlib,io,json,os,subprocess,sys,tarfile
from pathlib import Path
root=Path(ROOT);assert not root.exists();root.mkdir(mode=0o700)
body=sys.stdin.buffer.read();assert hashlib.sha256(body).hexdigest()==DIGEST
archive=root/'candidate.tar';archive.write_bytes(body);archive.chmod(0o600)
source=root/'addons';source.mkdir(mode=0o755)
with tarfile.open(fileobj=io.BytesIO(body)) as tar:
 for member in tar.getmembers():
  path=Path(member.name)
  assert not path.is_absolute() and '..' not in path.parts and not member.issym() and not member.islnk()
 tar.extractall(source)
subprocess.run(['/usr/bin/python3.10',str(source/'tools/community/build_simpledigital_candidate.py'),'--source',PROVIDER,'--output',str(source)],check=True)
(root/'candidate.json').write_text(json.dumps({'git_revision':REVISION,'archive_sha256':DIGEST,'owned_modules':MODULES,'production_changed':False},indent=2))
# Odoo's normal OS users can traverse only this dedicated rehearsal root.
root.chmod(0o755)
print('OPERATIONAL_CANDIDATE_STAGED '+str(root))
'''
    program = 'ROOT='+repr(args.root)+'\nDIGEST='+repr(digest)+'\nPROVIDER='+repr(PROVIDER)+'\nREVISION='+repr(revision)+'\nMODULES='+repr(modules)+'\n'+program
    command = 'sudo /usr/bin/python3.10 -u -c '+shlex.quote("exec(bytes.fromhex("+repr(program.encode().hex())+"))")
    subprocess.run(['ssh', 'odoo-new', command], input=body, check=True)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps({'root':args.root,'git_revision':revision,'archive_sha256':digest,
        'owned_modules':modules,'production_changed':False},indent=2),encoding='utf-8')


if __name__ == '__main__':
    main()
