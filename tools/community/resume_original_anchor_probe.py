"""Retry only a tool-corrected cohort probe, without modifying tested addons."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from offline_process import offline_odoo
from probe_original_handover import ADMISSION_SCOPES, admission_receipt_name, sealed_json


def parse_arguments(arguments=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('root','tools','source-visibility'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--admission-scope', choices=ADMISSION_SCOPES, default='full')
    parser.add_argument('--source-menu-visibility', type=Path)
    parser.add_argument('--source-menu-sha256')
    args = parser.parse_args(arguments)
    if args.source_menu_visibility is not None or args.source_menu_sha256 is not None:
        if (args.admission_scope != 'full' or args.source_menu_visibility is None
                or not re.fullmatch('[a-f0-9]{64}', args.source_menu_sha256 or '')):
            parser.error('Source menu witness requires full scope, explicit path and SHA256')
    return args


def main():
    import fcntl
    import pwd

    args=parse_arguments()
    root=args.root.resolve();tools=args.tools.resolve();stage=root/'anchor'
    assert os.geteuid()==0 and root.parent==Path('/opt/steps-validation') and root.name.startswith('community-original-handover-')
    assert tools.is_relative_to(Path('/opt/steps-validation')) and re.fullmatch('[A-Za-z0-9-]+',args.attempt)
    plan=json.loads((stage/'handover-plan.json').read_text());database=plan['database'];reference=plan['reference_database']
    assert re.fullmatch(r'MANAGEMENT_QA_CERRO_PAYROLL_API_ORIGINAL_HANDOVER_[A-Za-z0-9_]+',database)
    assert reference==database.replace('_HANDOVER_','_REFERENCE_') and json.loads((stage/'install-status.json').read_text())['exit_code']==0
    assert json.loads((stage/'loader-receipt.json').read_text())['original_cleanup_delegated'] is True
    if args.source_menu_visibility is not None:
        sealed_json(args.source_menu_visibility, args.source_menu_sha256)
    output=stage/('probe-'+args.attempt);assert not output.exists();output.mkdir(mode=0o750)
    actor=pwd.getpwnam('odoo');os.chown(output,actor.pw_uid,actor.pw_gid)
    visibility=output/'source-visibility.json';raw=args.source_visibility.read_bytes()
    with os.fdopen(os.open(visibility,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as stream:stream.write(raw)
    os.chown(visibility,actor.pw_uid,actor.pw_gid)
    source_menu = None
    if args.source_menu_visibility is not None:
        source_menu = output/'source-menu-visibility.json'; raw = args.source_menu_visibility.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == args.source_menu_sha256
        with os.fdopen(os.open(source_menu,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as stream:stream.write(raw)
        os.chown(source_menu,actor.pw_uid,actor.pw_gid)
    def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    receipt=output/admission_receipt_name(args.admission_scope)
    expression=('import sys,json,os;sys.path.insert(0,'+repr(str(tools))+'); from postcheck_original_anchor import run; '
        'result=run(env,'+repr(str(stage))+',database='+repr(database)+',reference='+repr(reference)
        +',capsule_sha256='+repr(sha(stage/'capsule.json'))+',identity_sha256='+repr(sha(stage/'identity-before.json'))
        +',source_visibility_path='+repr(str(visibility))+',source_visibility_sha256='+repr(sha(visibility))
        +',output_stage='+repr(str(output))+',admission_scope='+repr(args.admission_scope)
        +',source_menu_path='+repr(str(source_menu) if source_menu is not None else None)
        +',source_menu_sha256='+repr(args.source_menu_sha256)+');'
        +'assert result["data_projection_scope_passed"] is True;'
        +'assert result["admission_scope"]=='+repr(args.admission_scope)+';'
        +'env.cr.commit();result["transaction_committed"]=True;'
        +'f=os.fdopen(os.open('+repr(str(receipt))+',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),"w");'
        +'json.dump(result,f,indent=2);f.close();print("ORIGINAL_COHORT_SCOPE_OK")')
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
    assert status.returncode==0 and receipt.is_file(),'Private cohort probe rejected; inspect its new attempt directory'
    sealed=json.loads(receipt.read_text())
    assert sealed['admission_scope']==args.admission_scope and sealed['transaction_committed'] is True
    assert sealed['data_projection_scope_passed'] is True
    assert (sealed['ui_scope_exercised'],sealed['ui_admission']) == ((True,True)
        if args.admission_scope=='full' else (False,False))
    if source_menu is not None:
        assert all(sealed[name] is True for name in ('source_menu_witness_validated',
            'source_menu_visibility_parity','core_ui_admitted'))
    receipt.chmod(0o600)
    print('ORIGINAL_COHORT_SCOPE_OK',args.admission_scope,str(output),flush=True)


if __name__=='__main__':main()
