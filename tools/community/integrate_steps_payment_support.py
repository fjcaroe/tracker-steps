"""Combine the verified ticket and portal providers with the tested payments, documents and sales copy."""
import argparse
import fcntl
import gzip
import json
import os
from pathlib import Path
import subprocess

from admit_steps_fiscal_status import METADATA
from admit_steps_support_portal import release
from audit_steps_sales_schema import objects
from load_steps_sales_extension import guarded_command
from recover_steps_fiscal_fields import TARGET, WORK
from restore_converted_sys_cohort import check_modules, full_snapshot, save
from restore_steps_sales_backup import BASE
from restore_sys_previred_pair import LOCK, require


SUPPORT='step_helpdesk_tickets'
PORTAL='step_helpdesk_tickets_portal'
CORE='327c5bc269d9ee64dab3bd49735f350300552466c046a8013566636b3e99adad'
PORTAL_SHA='23d61b9f8c3ed1f4e9c59f238fe38b8ff45d75b41c3035acd1dac1fc7920d68a'
PAYMENTS='5428545ab11150a070894e1286480597925c2150856c5ba0344499a2b0c97db2'
RELEASES = {
    SUPPORT:(CORE,'18.0.1.0.2',BASE/'steps-sales-support-20261127U44H3/final-checkpoint/step_helpdesk_tickets.tar'),
    PORTAL:(PORTAL_SHA,'18.0.1.0.3',BASE/'steps-integrated-20261127U46A/support-portal-23d61b9f8c3e/portal.tar'),
}


def run(repeat):
    stage=WORK/'all-166'
    stage.mkdir(exist_ok=True)
    stage.chmod(0o755)
    require(Path(__file__).resolve().parent==WORK/'code' and stage.resolve(strict=True)==stage,'wrong-steps-166-target')
    payment=json.loads((WORK/'payment-cycle/repeat.json').read_bytes())
    require(payment['package']==PAYMENTS and payment['modules']==164 and payment['repeat'],'verified-payments-required')
    active=check_modules(TARGET)
    baseline=stage/'baseline.json.gz'
    if not baseline.exists():
        require(len(active)==164 and not (RELEASES.keys() & active.keys()),'wrong-restored-164-release')
        doc={'providers':active,'snapshot':full_snapshot(TARGET),'sql':objects(TARGET)}
        tmp=stage/'baseline.pending'
        tmp.write_bytes(gzip.compress(json.dumps(doc).encode()))
        tmp.replace(baseline)
    frozen=json.loads(gzip.decompress(baseline.read_bytes()))
    argv=json.loads((WORK/'private-args.json').read_bytes())
    require(argv[argv.index('-d')+1]==TARGET and '--net' in argv and '--no-http' in argv,'wrong-fiscal-profile')
    overlays=[str(release(name,archive,sha,stage)) for name,(sha,_version,archive) in RELEASES.items()]
    index,=[i for i,a in enumerate(argv) if a.startswith('--addons-path=')]
    rest=[path for path in argv[index].split('=',1)[1].split(',') if path not in overlays]
    require(rest[0]==str(WORK/'payment-cycle/releases'/PAYMENTS),'wrong-pending-payment-runtime')
    argv[index]='--addons-path='+','.join([*overlays,*rest])
    if repeat:
        require((stage/'install.json').is_file() and len(active)==166,'combined-166-installation-required')
    cmd=argv.copy()
    cmd.remove('shell')
    expected=dict(frozen['providers'])
    require(all(active.get(n)==v for n,v in expected.items()),'original-fiscal-module-drift')
    with (stage/'install.log').open('ab') as log:
        for name,(_sha,version,_archive) in RELEASES.items():
            expected[name]=[version,'LGPL-3']
            if repeat or name not in active:
                subprocess.run(guarded_command(cmd+['-u' if repeat else '-i',name],WORK,frozen['snapshot']),
                               stdout=log,stderr=log,check=True)
            require(check_modules(TARGET).get(name)==expected[name],'support-provider-version-drift')
    require(check_modules(TARGET)==expected and len(expected)==166,'incomplete-steps-166-release')
    after=full_snapshot(TARGET)
    before=frozen['snapshot']
    require(objects(TARGET)==frozen['sql'] and all(after[k]==before[k] for k in
            ('columns','constraints','relation_owner_and_acl','sequence_definitions')),'steps-166-schema-changed')
    require(before['public_tables'].keys()==after['public_tables'].keys(),'steps-166-tables-changed')
    changed={k for k,v in before['public_tables'].items() if v!=after['public_tables'][k]}
    require(changed<=METADATA|{'ir_act_window','ir_act_window_view','ir_ui_menu'},'steps-166-business-rows-changed-'+str(sorted(changed)))
    save(WORK/'private-args.json',argv)
    result={'database':TARGET,'modules':len(expected),'payment_package':PAYMENTS,'support_package':CORE,
            'portal_package':PORTAL_SHA,'repeat':repeat,'unchanged_tables':len(after['public_tables'])-len(changed),
            'changed_metadata':sorted(changed),'sql_objects':len(frozen['sql'])}
    save(stage/('repeat.json' if repeat else 'install.json'),result)
    print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeat',action='store_true')
    args=parser.parse_args()
    os.umask(0o077)
    with open(LOCK,'rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        run(args.repeat)
