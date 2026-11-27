"""Exercise a versioned support provider against the native ticket reference on a separate Steps restore."""
import argparse
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


TARGET = 'COMMUNITY_STEPS_CRM_SUPPORT_20261127U44H'
WORK = BASE/'steps-sales-support-20261127U44H'
MODULE = 'step_helpdesk_tickets'
FILES = ('__init__.py','__manifest__.py','hooks.py','models/__init__.py','models/tickets.py','views/tickets.xml')


def verify_inputs(checksum):
    archive = WORK/'support.tar'
    require(digest(archive)==checksum,'support-release-checksum')
    remaining = {MODULE+'/'+file for file in FILES}
    overlay = WORK/'package/addons'
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
    for path in (WORK/'package', overlay,*(p for p in overlay.rglob('*') if p.is_dir())):
        path.chmod(0o755)


def run(checksum):
    require(Path(__file__).resolve().parent==WORK/'code' and WORK.resolve(strict=True)==WORK,'private-support-directory')
    verify_inputs(checksum)
    frozen = restore(WORK,TARGET,checksum)
    command = odoo(shell=True,work=WORK,target=TARGET)
    (WORK/'private-args.json').write_text(json.dumps(command))
    def modules():
        return json.loads(query(TARGET,"SELECT json_object_agg(name,latest_version) FROM ir_module_module WHERE state='installed'"))
    expected = {n:p[1] for n,p in json.loads((SEALED/'effective-providers.json').read_bytes()).items()}
    require(len(expected)==157,'sales-baseline-required')
    if modules()==expected:
        upgrade = command.copy()
        upgrade.remove('shell')
        with (WORK/'install.log').open('ab') as log:
            subprocess.run(guarded_command(upgrade+['-i',MODULE],WORK,frozen),check=True,stdout=log,stderr=log)
    require(modules()=={**expected,MODULE:'18.0.1.0.0'},'support-provider-not-installed')
    observed = full_snapshot(TARGET)
    baseline = WORK/'before-trials.json'
    schema = definitions(TARGET,frozen,observed) if baseline.is_file() else audit(TARGET,frozen,observed)
    require(not any(schema['schema_changes'].values()),'original-support-schema-drift')
    protect = [key for key in frozen['public_tables'] if key.startswith(('helpdesk_','mail_'))]
    protect += ['res_groups_users_rel','res_company','res_partner','res_users','account_move','account_move_line',
                'ir_attachment','ir_rule','ir_model_access','crm_lead','sale_order','documents_document']
    for table in protect:
        require(frozen['public_tables'][table]==observed['public_tables'][table],'changed-business-data-'+table)
    if not baseline.exists():
        with baseline.open('x') as handle:
            json.dump(schema,handle)
    print(json.dumps({'database':TARGET,'modules':158,'release':checksum,'retained_tables':len(protect),'schema':schema}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('release_sha256')
    args=parser.parse_args()
    os.umask(0o077)
    with open(LOCK,'rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        run(args.release_sha256)
