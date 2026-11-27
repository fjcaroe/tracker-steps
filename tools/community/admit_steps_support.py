"""Exercise a versioned support provider against the native ticket reference on a separate Steps restore."""
import argparse
import ast
import fcntl
import json
import os
from pathlib import Path
import subprocess
import tarfile

from admit_steps_sales_documents import odoo
from audit_steps_sales_schema import audit, definitions
from custody_sys_previred_filestore import digest
from load_steps_sales_extension import guarded_command
from restore_converted_sys_cohort import full_snapshot
from restore_native_product_backup import query
from restore_steps_sales_backup import BASE, SEALED, restore
from restore_sys_previred_pair import LOCK, require


MODULE = 'step_helpdesk_tickets'
FILES = ('__init__.py','__manifest__.py','hooks.py','models/__init__.py','models/tickets.py','views/tickets.xml')


def verify_inputs(work, checksum):
    archive = work/'support.tar'
    require(digest(archive)==checksum,'support-release-checksum')
    remaining = {MODULE+'/'+file for file in FILES}
    overlay = work/'package/addons'
    with tarfile.open(archive) as package:
        for member in package:
            require(member.isfile() and member.name in remaining,'unexpected-support-release-member')
            remaining.remove(member.name)
            path = overlay/member.name
            path.parent.mkdir(parents=True,exist_ok=True)
            with package.extractfile(member) as src:
                data = src.read()
            if not path.exists():
                with path.open('xb') as out:
                    out.write(data)
            require(path.read_bytes()==data,'support-overlay-changed')
            path.chmod(0o644)
    require(not remaining and sum(p.is_file() for p in overlay.rglob('*'))==len(FILES),'support-source-incomplete')
    for path in (work/'package', overlay,*(p for p in overlay.rglob('*') if p.is_dir())):
        path.chmod(0o755)
    return ast.literal_eval((overlay/MODULE/'__manifest__.py').read_text())['version']


def run(checksum, batch, repeat=False):
    target = 'COMMUNITY_STEPS_CRM_SUPPORT_20261127'+batch
    work = BASE/('steps-sales-support-20261127'+batch)
    require(Path(__file__).resolve().parent==work/'code' and work.resolve(strict=True)==work,'private-support-directory')
    version = verify_inputs(work,checksum)
    require((batch,version) in (('U44H','18.0.1.0.0'),('U44H2','18.0.1.0.1')),'unexpected-ticket-release')
    frozen = restore(work,target,checksum)
    command = odoo(shell=True,work=work,target=target)
    args_file = work/'private-args.json'
    if not args_file.exists():
        with args_file.open('x') as out:
            json.dump(command,out)
    require(json.loads(args_file.read_bytes())==command,'private-arguments-changed')
    def modules():
        return json.loads(query(target,"SELECT json_object_agg(name,latest_version) FROM ir_module_module WHERE state='installed'"))
    expected = {n:p[1] for n,p in json.loads((SEALED/'effective-providers.json').read_bytes()).items()}
    require(len(expected)==157,'sales-baseline-required')
    baseline = work/'before-trials.json'
    installed = {**expected,MODULE:version}
    if repeat:
        require(batch=='U44H2' and baseline.is_file() and modules()==installed,'verified-first-install-required')
    if repeat or modules()==expected:
        upgrade = command.copy()
        upgrade.remove('shell')
        with (work/'install.log').open('ab') as log:
            subprocess.run(guarded_command(upgrade+['-u' if repeat else '-i',MODULE],work,frozen),check=True,stdout=log,stderr=log)
    require(modules()==installed,'support-provider-not-installed')
    observed = full_snapshot(target)
    schema = definitions(target,frozen,observed) if baseline.is_file() else audit(target,frozen,observed)
    require(not any(schema['schema_changes'].values()),'original-support-schema-drift')
    protect = [key for key in frozen['public_tables'] if key.startswith(('helpdesk_','mail_'))]
    protect += ['res_groups_users_rel','res_company','res_partner','res_users','account_move','account_move_line',
                'ir_attachment','ir_rule','ir_model_access','crm_lead','sale_order','documents_document']
    for table in protect:
        require(frozen['public_tables'][table]==observed['public_tables'][table],'changed-business-data-'+table)
    if not baseline.exists():
        with baseline.open('x') as handle:
            json.dump(schema,handle)
    print(json.dumps({'database':target,'modules':158,'release':checksum,'repeat':repeat,'retained_tables':len(protect),'schema':schema}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('release_sha256')
    parser.add_argument('--batch',choices=('U44H','U44H2'),default='U44H')
    parser.add_argument('--repeat',action='store_true')
    args=parser.parse_args()
    os.umask(0o077)
    with open(LOCK,'rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        run(args.release_sha256,args.batch,args.repeat)
