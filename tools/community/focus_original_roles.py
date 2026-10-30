"""Offline eight-case role/API diagnostic on an existing discarded private copy.

No install/upgrade, source restore or acceptance flag. Only two addon paths
change in a fresh overlay, to check actual group APIs before another full pair.
"""
import argparse
import configparser
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys

from offline_process import offline_odoo


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','reference','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--database',required=True)
    args=parser.parse_args();source=args.source.resolve();reference=args.reference.resolve();output=args.output.resolve()
    assert os.geteuid()==0 and re.fullmatch(r'MANAGEMENT_QA_CERRO_PAYROLL_API_CRITICAL_[A-Za-z0-9_]+',args.database)
    assert all(path.is_relative_to(Path('/opt/steps-validation')) for path in (source,reference,output))
    assert not output.exists() and (reference/'data').is_dir()
    conf=configparser.ConfigParser(interpolation=None);assert conf.read('/etc/odoo18-cerroelplomo.conf')
    assert conf['options']['db_name']=='CERRO_EL_PLOMO'
    output.mkdir(mode=0o750);overlay=output/'addons';overlay.mkdir(mode=0o755)
    modules=('step_payroll_contracts','step_payroll_benefits_native_reference')
    fingerprints={}
    for name in modules:
        assert (source/name/'__manifest__.py').is_file()
        (overlay/name).symlink_to(source/name)
        fingerprints.update({name+'/'+p.relative_to(source/name).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (source/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts})
    owner=pwd.getpwnam('cerro_odoo18');os.chown(output,owner.pw_uid,owner.pw_gid)
    paths=','.join((str(overlay),str(reference/'addons'),conf['options']['addons_path']))
    command=['sudo','-u','cerro_odoo18','/usr/bin/python3.10',str(source/'tools/ops/run_agriculture_upgrade.py'),
        '-c','/etc/odoo18-cerroelplomo.conf','-d',args.database,'--db-filter=^'+args.database+'$',
        '--db_host=/var/run/postgresql','--addons-path='+paths,'--data-dir='+str(reference/'data'),
        '--load=base,web','--workers=0','--max-cron-threads=0','--without-demo=all','--no-http','--stop-after-init',
        '--test-enable','--test-tags=/step_payroll_benefits_native_reference:NativeBenefitReferenceCase',
        '--logfile='+str(output/'tests.log')]
    with open('/run/lock/steps-environments.lock','a') as lease:
        print('ORIGINAL_ROLES_FOCUS_WAITING_FOR_LEASE',flush=True);fcntl.flock(lease,fcntl.LOCK_EX)
        with (output/'bootstrap.log').open('x') as log:
            result=subprocess.run(offline_odoo(command),stdout=log,stderr=subprocess.STDOUT)
    text=(output/'tests.log').read_text(errors='replace')
    summaries=re.findall(r'([0-9]+) failed, ([0-9]+) error\(s\) of ([0-9]+) tests',text)
    okay=result.returncode==0 and summaries==[('0','0','8')] and not re.search(r' (ERROR|CRITICAL) ',text)
    proof={'database':args.database,'tests':summaries,'exit_code':result.returncode,'functional_diagnostic_passed':okay,
        'source_files':fingerprints,'install_or_upgrade_requested':False,'full_acceptance':False,'production_changed':False}
    (output/'diagnostic.json').write_text(json.dumps(proof,indent=2));(output/'diagnostic.json').chmod(0o600)
    print('ORIGINAL_ROLES_FOCUS',summaries,flush=True)
    assert okay,'Inspect private focused logs; full migration not accepted'


if __name__=='__main__':main()
