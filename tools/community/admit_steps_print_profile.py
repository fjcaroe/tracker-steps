"""Install the historical print colors on a private restore of the checked Steps CRM and sales release."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import tarfile

from audit_steps_sales_schema import audit
from custody_sys_previred_filestore import digest
from load_steps_sales_extension import guarded_command
from restore_converted_sys_cohort import full_snapshot
from restore_native_product_backup import query
from restore_steps_sales_backup import BASE, CRM, SEALED, SQL_SHA, restore
from restore_sys_previred_pair import LOCK, require


WORK = BASE/'steps-sales-print-20261127U43Y'
TARGET = 'COMMUNITY_STEPS_CRM_PRINT_20261127U43Y'
MODULE = 'step_report_print_colors'
RELEASE = 'db1f4c20809563d81e759b2d03c76b1ed57f547d02e4b320eca7901f4cc19dc9'


def install_colors(package, overlay):
    require(digest(package) == RELEASE,'print-release-differs')
    paths = {MODULE+'/'+name for name in ('__init__.py','__manifest__.py','static/src/scss/print_colors.scss')}
    with tarfile.open(package) as bundle:
        for member in bundle:
            require(member.isfile() and member.name in paths, 'unexpected-print-file')
            paths.remove(member.name)
            file = overlay/member.name
            file.parent.mkdir(parents=True,exist_ok=True)
            with bundle.extractfile(member) as content:
                data = content.read()
            if not file.exists():
                with file.open('xb') as out:
                    out.write(data)
            require(file.read_bytes()==data,'changed-private-print-source')
            file.chmod(0o644)
    require(not paths and len([p for p in overlay.rglob('*') if p.is_file()])==3, 'incomplete-print-release')
    for directory in (overlay,*(p for p in overlay.rglob('*') if p.is_dir())):
        directory.chmod(0o755)


def run():
    require(WORK.resolve(strict=True) == WORK and Path(__file__).resolve().parent == WORK/'code',
            'private-print-area-required')
    package = WORK/'package.tar'
    require(digest(package) == RELEASE,'print-release-differs')
    frozen = restore(WORK,TARGET,RELEASE)
    overlay = WORK/'addons'
    install_colors(package,overlay)
    old_root = CRM/'quote-20261127U42A'
    command = json.loads((old_root/'private-args.json').read_bytes())
    old_db = 'COMMUNITY_STEPS_CRM_QUOTE_20261127U42A'
    require(command[command.index('-d')+1]==old_db and '--db-filter=^'+old_db+'$' in command,'wrong-template')
    command = [item.replace(old_db,TARGET).replace(str(old_root/'data'),str(WORK/'data')) for item in command]
    binary = command.index('shell')-1
    require(command[binary].endswith('/odoo-bin'),'unexpected-original-executable')
    command[binary] = str(SEALED/'runtime/odoo-bin')
    index, = [i for i,arg in enumerate(command) if arg.startswith('--addons-path=')]
    command[index] = '--addons-path='+','.join(map(str,(overlay,SEALED/'runtime/addons',SEALED/'runtime/odoo/addons')))
    (WORK/'private-args.json').write_text(json.dumps(command))
    def modules():
        return json.loads(query(TARGET,"SELECT json_object_agg(name,latest_version) FROM ir_module_module WHERE state='installed'"))
    expected = {key:value[1] for key,value in json.loads((SEALED/'effective-providers.json').read_bytes()).items()}
    require(len(expected)==157,'wrong-sales-baseline')
    if modules()==expected:
        upgrade = command.copy()
        upgrade.remove('shell')
        with (WORK/'install.log').open('ab') as private:
            subprocess.run(guarded_command([*upgrade,'--without-demo=all','-i',MODULE], WORK, frozen),
                           check=True,stdout=private,stderr=private)
    require(modules()=={**expected,MODULE:'18.0.1.0.0'},'print-module-not-installed')
    after = full_snapshot(TARGET)
    schema_check = audit(TARGET,frozen,after)
    require(not any(schema_check['schema_changes'].values()),'original-print-schema-drift')
    protected = ('sale_order','sale_order_line','crm_lead','res_partner','res_company','res_users',
                 'res_groups_users_rel','account_move','account_move_line','account_payment','mail_mail',
                 'documents_document','documents_access','helpdesk_ticket','ir_rule','ir_model_access')
    require(all(frozen['public_tables'][t]==after['public_tables'][t] for t in protected),'sales-or-rights-changed')
    result = {'sql':SQL_SHA,'release':RELEASE,'installed':158,'protected_tables':len(protected),'schema':schema_check}
    print(json.dumps(result),flush=True)


if __name__ == '__main__':
    os.umask(0o077)
    with open(LOCK,'rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        run()
