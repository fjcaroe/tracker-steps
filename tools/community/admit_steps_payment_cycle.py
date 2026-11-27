"""Install the tested pending-payment workflow only on a restored Steps accounting database."""
import argparse
import ast
import fcntl
import gzip
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile

from admit_steps_fiscal_status import METADATA, MODULE as FISCAL_HISTORY
from audit_steps_sales_schema import objects
from custody_sys_previred_filestore import digest
from load_steps_sales_extension import guarded_command
from recover_steps_fiscal_fields import TARGET, WORK
from restore_converted_sys_cohort import check_modules, full_snapshot, save
from restore_sys_previred_pair import LOCK, require


MODULE='step_payment_in_process'
FISCAL_VERSION='18.0.1.0.3'
MEMBERS={'__init__.py','__manifest__.py','account_move.py'}


def release(sha, area):
    require(re.fullmatch('[0-9a-f]{64}',sha),'invalid-payment-provider-digest')
    archive=area/(sha+'.tar')
    require(digest(archive)==sha,'pending-payment-source-differs')
    addons=area/'releases'/sha
    dest=addons/MODULE
    dest.mkdir(parents=True,exist_ok=True)
    for path in (area,addons.parent,addons,dest):
        path.chmod(0o755)
    with tarfile.open(archive,'r:') as package:
        members=package.getmembers()
        require(len(members)==3 and {m.name for m in members}=={MODULE+'/'+name for name in MEMBERS}
                and all(m.isfile() for m in members),'unexpected-payment-package')
        for member in members:
            path=addons/member.name
            data=package.extractfile(member).read()
            if not path.exists():
                with path.open('xb') as handle:
                    handle.write(data)
                path.chmod(0o644)
            require(path.resolve(strict=True)==path and path.read_bytes()==data,'changed-payment-source')
    require({p.name for p in dest.iterdir()}==MEMBERS,'unexpected-payment-source-file')
    info=ast.literal_eval((dest/'__manifest__.py').read_text())
    require(info['depends']==['account'] and info['version']=='18.0.1.0.0' and info['license']=='LGPL-3',
            'incorrect-payment-release-contract')
    return addons


def run(sha,repeat):
    require(Path(__file__).resolve().parent==WORK/'code','incorrect-private-payment-target')
    area=WORK/'payment-cycle'
    addons=release(sha,area)
    argv=json.loads((WORK/'private-args.json').read_bytes())
    require(argv[argv.index('-d')+1]==TARGET and '--no-http' in argv and '--net' in argv,'expected-isolated-financial-copy')
    base=area/'base.json.gz'
    previous=check_modules(TARGET)
    require(previous.get(FISCAL_HISTORY)==[FISCAL_VERSION,'LGPL-3'] and len(previous) in (163,164),'wrong-financial-source')
    if not base.exists():
        require(len(previous)==163 and MODULE not in previous,'unmodified-payment-source-required')
        baseline={'rows':full_snapshot(TARGET),'sql':objects(TARGET),'providers':previous}
        tmp=base.with_suffix('.new')
        tmp.write_bytes(gzip.compress(json.dumps(baseline).encode()))
        tmp.replace(base)
    frozen=json.loads(gzip.decompress(base.read_bytes()))
    ix,=[i for i,arg in enumerate(argv) if arg.startswith('--addons-path=')]
    roots=argv[ix].split('=',1)[1].split(',')
    if roots[0]!=str(addons):
        require(roots[0].startswith(str(WORK/'releases')+'/'),'unexpected-current-payment-overlay')
        argv[ix]='--addons-path='+','.join([str(addons),*roots])
    if repeat:
        require(json.loads((area/'install.json').read_bytes())['package']==sha and MODULE in previous,
                'install-before-payment-update')
    if MODULE not in previous or repeat:
        cmd=argv.copy()
        cmd.remove('shell')
        with (area/'install.log').open('ab') as log:
            subprocess.run(guarded_command(cmd+['-u' if repeat else '-i',MODULE],WORK,frozen['rows']),
                           check=True,stdout=log,stderr=log)
    final=check_modules(TARGET)
    require(final=={**frozen['providers'],MODULE:['18.0.1.0.0','LGPL-3']},'unexpected-integrated-payment-modules')
    snap=full_snapshot(TARGET)
    require(objects(TARGET)==frozen['sql'] and all(snap[k]==frozen['rows'][k] for k in
            ('columns','constraints','sequence_definitions','relation_owner_and_acl')),'payment-schema-changed')
    before=frozen['rows']['public_tables']
    require(before.keys()==snap['public_tables'].keys(),'payment-tables-changed')
    changed={k for k,v in before.items() if snap['public_tables'][k]!=v}
    require(changed<=METADATA,'payment-business-rows-changed-'+str(sorted(changed-METADATA)))
    save(WORK/'private-args.json',argv)
    result={'database':TARGET,'modules':len(final),'protected_tables':len(before)-len(changed),
            'changed_metadata':sorted(changed),'package':sha,'repeat':repeat}
    save(area/('repeat.json' if repeat else 'install.json'),result)
    print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sha')
    parser.add_argument('--repeat',action='store_true')
    args=parser.parse_args()
    os.umask(0o077)
    with open(LOCK,'rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        run(args.sha,args.repeat)
