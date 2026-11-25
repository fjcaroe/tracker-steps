"""Upload only committed free-owned sources into a new original-cohort sandbox."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess

from build_original_anchor_profile import OWN


def stage(root, receipt, *, original_storage=False, schema_plan=None):
    assert re.fullmatch(r'/opt/steps-validation/community-original-handover-[A-Za-z0-9-]+', root)
    assert type(original_storage) is bool and (schema_plan is not None) is original_storage
    if schema_plan is not None:
        assert str(schema_plan).startswith('/opt/steps-validation/') and str(schema_plan).endswith('.json')
    repo = Path(__file__).resolve().parents[2]
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip()
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    body = subprocess.check_output(['git', 'archive', revision, *OWN, 'tools/community', 'tools/ops'], cwd=repo)
    digest = hashlib.sha256(body).hexdigest()
    program = '''from pathlib import Path
import sys,io,tarfile,hashlib,subprocess,json,os
root=Path(ROOT);assert not root.exists();root.mkdir(mode=0o755)
raw=sys.stdin.buffer.read();assert hashlib.sha256(raw).hexdigest()==DIGEST
(root/'candidate.tar').write_bytes(raw);(root/'candidate.tar').chmod(0o600)
source=root/'source';source.mkdir(mode=0o755)
with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
 for m in archive.getmembers():
  assert not Path(m.name).is_absolute() and '..' not in Path(m.name).parts and (m.isdir() or m.isfile())
 archive.extractall(source)
subprocess.run(['/usr/bin/python3.10',str(source/'tools/community/build_original_anchor_profile.py'),
 '--root',str(root),'--runtime','/opt/steps-validation/community-foundation-final-20261027/community-runtime',
 '--oca','/opt/steps-validation/community-hr-payroll-audit-20261027/oca-payroll',
 '--provider','/opt/steps-managed/payroll/cerro/2dc161f26c6d549a00c474bf81e8c3f83e984092/l10n_cl_simpledigital_payroll']
 +(['--original-storage','--schema-plan',SCHEMA_PLAN] if ORIGINAL_STORAGE else []),check=True)
(root/'candidate.json').write_text(json.dumps({'git_revision':REVISION,'archive_sha256':DIGEST,'production_changed':False},indent=2));(root/'candidate.json').chmod(0o600)
print('ORIGINAL_ANCHOR_STAGED',root)
'''
    program = 'ROOT='+repr(root)+'\nDIGEST='+repr(digest)+'\nREVISION='+repr(revision)+'\nORIGINAL_STORAGE='+repr(original_storage)+'\nSCHEMA_PLAN='+repr(str(schema_plan) if schema_plan else None)+'\n'+program
    command = 'sudo /usr/bin/python3.10 -c ' + shlex.quote('exec(bytes.fromhex('+repr(program.encode().hex())+'))')
    subprocess.run(['ssh', 'odoo-new', command], input=body, check=True)
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps({'root':root,'git_revision':revision,'archive_sha256':digest,
        'database_created':False,'production_changed':False},indent=2),encoding='utf-8')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True);parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--original-storage',action='store_true');parser.add_argument('--schema-plan')
    args=parser.parse_args();stage(args.root,args.receipt,original_storage=args.original_storage,schema_plan=args.schema_plan)
