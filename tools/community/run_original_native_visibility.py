"""Run the actual native control registry entirely read-only, under the lease."""
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

from offline_process import offline_odoo


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--tools',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=args.root.resolve();tools=args.tools.resolve();stage=root/'anchor'
    assert os.geteuid()==0 and root.parent==Path('/opt/steps-validation')
    assert root.name.startswith('community-original-handover-') and tools.is_relative_to(Path('/opt/steps-validation'))
    plan=json.loads((stage/'handover-plan.json').read_text());database=plan['reference_database']
    assert re.fullmatch(r'MANAGEMENT_QA_CERRO_PAYROLL_API_ORIGINAL_REFERENCE_[A-Za-z0-9_]+',database)
    assert database==plan['database'].replace('_HANDOVER_','_REFERENCE_')
    actor=json.loads((stage/'cohort-probe.json').read_text())['actor']
    assert actor['superuser'] is False and actor['users_created'] is False and actor['permissions_granted'] is False
    output=args.output.resolve()
    assert output.parent==Path('/opt/steps-validation') and output.name.startswith('community-native-visibility-')
    assert not output.exists();output.mkdir(mode=0o750)
    owner=pwd.getpwnam('cerro_odoo18');os.chown(output,owner.pw_uid,owner.pw_gid)
    data=output/'data';data.mkdir(mode=0o750);os.chown(data,owner.pw_uid,owner.pw_gid)
    source=configparser.ConfigParser(interpolation=None);assert source.read('/etc/odoo18-cerroelplomo.conf')
    assert source['options']['db_name']=='CERRO_EL_PLOMO'
    capsule=output/'capsule.json';body=(stage/'capsule.json').read_bytes()
    with os.fdopen(os.open(capsule,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as stream:stream.write(body)
    os.chown(capsule,owner.pw_uid,owner.pw_gid);digest=hashlib.sha256(body).hexdigest()
    expression=('import sys;sys.path.insert(0,'+repr(str(tools))+'); '
        'from probe_original_master_visibility import run; result=run(env,'+repr(str(capsule))+','+repr(digest)
        +',actor_uid='+repr(actor['uid'])+',company_ids='+repr(actor['allowed_company_ids'])
        +',active_company_id='+repr(actor['active_company_id'])+',output='+repr(str(output/'source.json'))
        +'); print("NATIVE_MASTER_VISIBILITY",result["allowed_master_ids"],result["denied_master_ids"])')
    command=['sudo','-u','cerro_odoo18','/usr/bin/python3.10',str(tools/'original_external_references_readonly_bootstrap.py'),
        '/opt/odoo18','/opt/odoo18/odoo-bin',database,'shell','-c','/etc/dev_odoo18.conf',
        '-d',database,'--db-filter=^'+database+'$','--db_host=/var/run/postgresql',
        '--addons-path='+source['options']['addons_path'],'--data-dir='+str(data),'--load=base,web',
        '--workers=0','--max-cron-threads=0','--no-http','--without-demo=all','--stop-after-init',
        '--logfile='+str(output/'native.log')]
    with open('/run/lock/steps-environments.lock','a') as lease:
        print('ORIGINAL_NATIVE_VISIBILITY_WAITING_FOR_LEASE',flush=True);fcntl.flock(lease,fcntl.LOCK_EX)
        with (output/'bootstrap.log').open('x') as log:
            result=subprocess.run(offline_odoo(command),input=expression,text=True,stdout=log,stderr=subprocess.STDOUT)
    assert result.returncode==0 and (output/'source.json').is_file(),'Native readonly visibility probe rejected; inspect private logs'
    value=json.loads((output/'source.json').read_text())
    print('ORIGINAL_NATIVE_VISIBILITY',value['allowed_master_ids'],value['denied_master_ids'],flush=True)


if __name__=='__main__':main()
