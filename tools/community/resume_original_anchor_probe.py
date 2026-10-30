"""Retry only a tool-corrected cohort probe, without modifying tested addons."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import subprocess

from offline_process import offline_odoo


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('root','tools','source-visibility'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--attempt',required=True);args=parser.parse_args()
    root=args.root.resolve();tools=args.tools.resolve();stage=root/'anchor'
    assert os.geteuid()==0 and root.parent==Path('/opt/steps-validation') and root.name.startswith('community-original-handover-')
    assert tools.is_relative_to(Path('/opt/steps-validation')) and re.fullmatch('[A-Za-z0-9-]+',args.attempt)
    plan=json.loads((stage/'handover-plan.json').read_text());database=plan['database'];reference=plan['reference_database']
    assert re.fullmatch(r'MANAGEMENT_QA_CERRO_PAYROLL_API_ORIGINAL_HANDOVER_[A-Za-z0-9_]+',database)
    assert reference==database.replace('_HANDOVER_','_REFERENCE_') and json.loads((stage/'install-status.json').read_text())['exit_code']==0
    assert json.loads((stage/'loader-receipt.json').read_text())['original_cleanup_delegated'] is True
    output=stage/('probe-'+args.attempt);assert not output.exists();output.mkdir(mode=0o750)
    actor=pwd.getpwnam('odoo');os.chown(output,actor.pw_uid,actor.pw_gid)
    visibility=output/'source-visibility.json';raw=args.source_visibility.read_bytes()
    with os.fdopen(os.open(visibility,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as stream:stream.write(raw)
    os.chown(visibility,actor.pw_uid,actor.pw_gid)
    def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    expression=('import sys,json;sys.path.insert(0,'+repr(str(tools))+'); from postcheck_original_anchor import run; '
        'result=run(env,'+repr(str(stage))+',database='+repr(database)+',reference='+repr(reference)
        +',capsule_sha256='+repr(sha(stage/'capsule.json'))+',identity_sha256='+repr(sha(stage/'identity-before.json'))
        +',source_visibility_path='+repr(str(visibility))+',source_visibility_sha256='+repr(sha(visibility))
        +',output_stage='+repr(str(output))+');env.cr.commit();open('+repr(str(output/'cohort-admission.json'))
        +',"x").write(json.dumps(result,indent=2));print("ORIGINAL_COHORT_PARITY_OK")')
    runtime=Path('/opt/steps-validation/community-foundation-final-20261027/community-runtime')
    paths=','.join(map(str,(root/'runtime-addons',root/'engine-addons',runtime/'addons')))
    command=['sudo','-u','odoo','/usr/bin/python3.10',str(runtime/'odoo-bin'),'shell',
        '-c','/etc/dev_odoo18.conf','-d',database,'--db-filter=^'+database+'$','--db_host=/var/run/postgresql',
        '--addons-path='+paths,'--data-dir='+str(stage/'data'),'--load=base,web','--workers=0','--max-cron-threads=0',
        '--without-demo=all','--no-http','--logfile='+str(output/'cohort.log')]
    with open('/run/lock/steps-environments.lock','a') as lease:
        print('ORIGINAL_COHORT_PARITY_WAITING_FOR_LEASE',flush=True);fcntl.flock(lease,fcntl.LOCK_EX)
        with (output/'bootstrap.log').open('x') as log:
            status=subprocess.run(offline_odoo(command),input=expression,text=True,stdout=log,stderr=subprocess.STDOUT)
    assert status.returncode==0 and (output/'cohort-admission.json').is_file(),'Private cohort probe rejected; inspect its new attempt directory'
    (output/'cohort-admission.json').chmod(0o600)
    print('ORIGINAL_COHORT_PARITY_OK',str(output),flush=True)


if __name__=='__main__':main()
