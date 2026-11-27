"""Install or update the historical DTE field after restoring the original Chilean dependencies."""
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

from audit_steps_sales_schema import objects
from custody_sys_previred_filestore import digest
from load_steps_sales_extension import guarded_command
from recover_steps_fiscal_fields import CONTRACTS, SEALED, SOURCE, SQL_SHA, TARGET, WORK
from restore_converted_sys_cohort import check_modules, full_snapshot
from restore_native_product_backup import query
from restore_sys_previred_pair import LOCK, require


MODULE = 'step_cl_invoice_status_history'
FILES = {'__init__.py','__manifest__.py','hooks.py','models/__init__.py','models/account_move.py','views/account_move.xml'}
METADATA = {'ir_model','ir_model_fields','ir_model_fields_selection','ir_model_data','ir_ui_view',
            'ir_module_module','ir_module_module_dependency','ir_cron_trigger','ir_model_constraint'}


def install_payload(checksum):
    require(re.fullmatch('[a-f0-9]{64}',checksum),'invalid-fiscal-package-checksum')
    archive=WORK/('status-'+checksum+'.tar')
    require(digest(archive)==checksum,'incorrect-fiscal-package')
    folder=WORK/'addons'/MODULE
    members=set()
    with tarfile.open(archive) as package:
        for entry in package:
            key=Path(entry.name)
            require(entry.isfile() and key.parts[0]==MODULE and key.relative_to(MODULE).as_posix() in FILES
                    and key not in members,'unexpected-fiscal-package-member')
            members.add(key)
            target=WORK/'addons'/key
            target.parent.mkdir(parents=True,exist_ok=True)
            data=package.extractfile(entry).read()
            if not target.exists():
                with target.open('xb') as handle:
                    handle.write(data)
            require(target.resolve(strict=True)==target and target.read_bytes()==data,'fiscal-source-changed')
            target.chmod(0o644)
    require(len(members)==len(FILES) and {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}==FILES,
            'incomplete-fiscal-package')
    for path in [folder,*(p for p in folder.rglob('*') if p.is_dir())]:
        path.chmod(0o755)
    manifest=ast.literal_eval((folder/'__manifest__.py').read_text())
    require(manifest['version']=='18.0.1.0.0' and manifest['license']=='LGPL-3' and manifest['depends']==['l10n_cl'],
            'unexpected-historical-provider')


def run(checksum,repeat):
    require(Path(__file__).resolve().parent==WORK/'code' and WORK.resolve(strict=True)==WORK
            and digest(SEALED/'source.dump')==SQL_SHA,'expected-steps-fiscal-source')
    install_payload(checksum)
    frozen=json.loads(gzip.decompress((SEALED/'source-snapshot.json.gz').read_bytes()))
    argv=json.loads((WORK/'private-args.json').read_bytes())
    require(argv[argv.index('-d')+1]==TARGET and '--no-http' in argv,'incorrect-fiscal-database')
    names=json.loads((SEALED/'effective-providers.json').read_bytes()).keys()|CONTRACTS.keys()
    baseline=WORK/'status-install.json'
    active=check_modules(TARGET)
    if repeat:
        require(baseline.is_file() and json.loads(baseline.read_bytes())['package']==checksum and active.keys()==names|{MODULE},
                'tested-package-required-for-update')
    if repeat or active.keys()==names:
        command=argv.copy()
        command.remove('shell')
        with (WORK/'status-install.log').open('ab') as log:
            subprocess.run(guarded_command(command+['-u' if repeat else '-i',MODULE],WORK,frozen),check=True,stdout=log,stderr=log)
    current=check_modules(TARGET)
    require(current.keys()==names|{MODULE} and current[MODULE]==['18.0.1.0.0','LGPL-3'],'historical-fiscal-provider-unavailable')
    snapshot=full_snapshot(TARGET)
    require(all(frozen[k]==snapshot[k] for k in ('columns','constraints','sequence_definitions','relation_owner_and_acl'))
            and objects(TARGET)==objects(SOURCE),'original-fiscal-schema-differs')
    changed={t for t,v in frozen['public_tables'].items() if snapshot['public_tables'].get(t)!=v}
    require(changed<=METADATA and frozen['public_tables'].keys()==snapshot['public_tables'].keys(),
            'original-fiscal-business-data-changed-'+str(sorted(changed-METADATA)))
    require(query(TARGET,"SELECT count(*) FROM account_move WHERE l10n_cl_dte_status IS NOT NULL")=='23',
            'original-dte-status-count')
    result={'target':TARGET,'package':checksum,'modules':len(current),'repeat':repeat,
            'protected_tables':len(frozen['public_tables'])-len(changed),'changed_metadata':sorted(changed),
            'stored_dte_statuses':23,'source':SQL_SHA}
    if not baseline.exists():
        with baseline.open('x') as handle:
            json.dump(result,handle)
    print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checksum')
    parser.add_argument('--repeat',action='store_true')
    args=parser.parse_args()
    os.umask(0o077)
    with open(LOCK,'rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        run(args.checksum,args.repeat)
