"""Install the verified historical document library on an independent restore of the Steps sales backup."""
import argparse
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import tarfile

from audit_steps_sales_schema import audit
from admit_steps_print_profile import MODULE as COLORS, RELEASE as COLORS_SHA, install_colors
from custody_sys_previred_filestore import digest
from load_steps_sales_extension import guarded_command
from restore_converted_sys_cohort import full_snapshot
from restore_native_product_backup import query
from restore_steps_sales_backup import BASE, CRM, SEALED, SQL_SHA, restore
from restore_sys_previred_pair import LOCK, require


TARGET = 'COMMUNITY_STEPS_CRM_DOC_20261127U43X'
WORK = BASE/'steps-sales-library-20261127U43X'
COMBINED = 'COMMUNITY_STEPS_CRM_DOC_20261127U44P'
COMBINED_WORK = BASE/'steps-sales-library-20261127U44P'
REFERENCE = CRM/'native/library-20261127U43A/receipts'
PACKAGE = BASE/'community-document-portal-20261126U41P/folders-f2ea467610be/package.tar'
MODULES = {'step_document_library': '18.0.1.0.5', 'step_document_library_portal': '18.0.1.0.3'}
DOCUMENT_SHA = 'c8548015d864c1bac5b7b0a6d8eef588d2cfb4a29ed31132309f2b2e032c1b88'


def install_code(work):
    require(digest(PACKAGE) == DOCUMENT_SHA, 'checked-document-release-required')
    overlay = work/'package'
    files = set()
    with tarfile.open(PACKAGE) as bundle:
        for item in bundle:
            name = Path(item.name)
            require(name.parts and name.parts[0] == 'addons' and '..' not in name.parts
                    and (len(name.parts) == 1 or name.parts[1] in MODULES), 'unexpected-package-path')
            if item.isdir():
                continue
            require(item.isfile() and len(name.parts) >= 3 and name not in files, 'unexpected-package-file')
            files.add(name)
            dest = overlay/name
            dest.parent.mkdir(parents=True, exist_ok=True)
            with bundle.extractfile(item) as src:
                raw = src.read()
            if not dest.exists():
                with dest.open('xb') as out:
                    out.write(raw)
            require(dest.read_bytes() == raw, 'overlay-drift')
            dest.chmod(0o644)
    require(files == {p.relative_to(overlay) for p in overlay.rglob('*') if p.is_file()}, 'unexpected-overlay')
    for folder in (overlay, *(p for p in overlay.rglob('*') if p.is_dir())):
        folder.chmod(0o755)


def odoo(shell=False, *, work=WORK, target=TARGET):
    core = SEALED/'runtime'
    overlays = [work/'package/addons']
    if target == COMBINED:
        overlays.append(work/'print-addons')
    addons = ','.join(map(str, [*overlays,core/'addons',core/'odoo/addons']))
    return ['unshare','--net','--','sh','-ec','ip link set dev lo up; exec "$@"','steps',
            'runuser','-u','odoo','--','env','PYTHONDONTWRITEBYTECODE=1','/usr/bin/python3.10',str(core/'odoo-bin'),
            *(['shell'] if shell else []),'-c','/etc/odoo18.conf','-d',target,'--db-filter=^'+target+'$',
            '--db_host=/var/run/postgresql','--data-dir='+str(work/'data'),'--addons-path='+addons,
            '--no-http','--workers=0','--max-cron-threads=0','--without-demo=all','--stop-after-init',
            '--load=base,web','--logfile='+str(work/'data/odoo.log')]


def original_rows(target, table, *, remove=(), maximum_id=None):
    permitted = {'documents_document','ir_rule','ir_model_access','ir_attachment'}
    require(table in permitted, 'unexpected-projection')
    projection = 'to_jsonb(r)' + ''.join(" - '"+key+"'" for key in remove)
    limit = '' if maximum_id is None else f'WHERE id<={int(maximum_id)}'
    return json.loads(query(target,f"""SET TIME ZONE 'UTC';
        SELECT json_build_array(count(*),encode(sha256(convert_to(coalesce(string_agg(h,'' ORDER BY h),''),
            'UTF8')),'hex')) FROM (SELECT encode(sha256(convert_to(({projection})::text,
            'UTF8')),'hex') h FROM ONLY public.{table} r {limit}) original"""))


def run(with_print=False):
    work,target = (COMBINED_WORK,COMBINED) if with_print else (WORK,TARGET)
    require(work.resolve(strict=True) == work and work.parent == BASE and
            Path(__file__).resolve().parent == work/'code','private-directory-required')
    matrix = json.loads((REFERENCE/'matrix.json').read_bytes())
    require(len(set(matrix['documents'])) == 98, 'original-steps-permissions-required')
    release = sha256((DOCUMENT_SHA+COLORS_SHA).encode()).hexdigest() if with_print else DOCUMENT_SHA
    frozen = restore(work,target,release)
    install_code(work)
    extensions = dict(MODULES)
    if with_print:
        install_colors(work/'print.tar',work/'print-addons')
        extensions[COLORS] = '18.0.1.0.0'
    command_file = work/'private-args.json'
    command = odoo(True,work=work,target=target)
    if not command_file.exists():
        with command_file.open('x') as output:
            json.dump(command,output)
    require(json.loads(command_file.read_bytes()) == command,'private-startup-command-differs')
    def installed():
        return json.loads(query(target,"SELECT json_object_agg(name,latest_version) FROM ir_module_module WHERE state='installed'"))
    old = installed()
    original = json.loads((SEALED/'effective-providers.json').read_bytes())
    expected = {key:value[1] for key,value in original.items()}
    require(len(expected)==157, 'crm-profile-required')
    high_water = work/'original-policy-ids.json'
    if not high_water.exists():
        require(old == expected, 'policy-baseline-before-install-required')
        limits = {table:int(query(target,'SELECT max(id) FROM '+table))
                  for table in ('ir_rule','ir_model_access','ir_attachment')}
        with high_water.open('x') as handle:
            json.dump(limits, handle)
    limits = json.loads(high_water.read_bytes())
    if old == expected:
        with (work/'install.log').open('ab') as log:
            upgrade = odoo(work=work,target=target) + ['-i',','.join(extensions)]
            subprocess.run(guarded_command(upgrade, work, frozen),
                           stdout=log,stderr=log,check=True)
    require(installed() == {**expected,**extensions},'combined-module-versions-differ')
    raw_before = full_snapshot(target)
    schema_check = audit(target,frozen,raw_before)
    require(not any(schema_check['schema_changes'].values()),'original-library-schema-drift')
    protected = ('sale_order','sale_order_line','crm_lead','helpdesk_ticket','hr_employee','res_partner',
                 'account_move','account_move_line','account_payment','documents_access','mail_mail',
                 'res_users','res_groups_users_rel')
    for table in protected:
        require(raw_before['public_tables'][table] == frozen['public_tables'][table],'changed-original-table-'+table)
    catalogs = {key:json.loads((REFERENCE/(key+'.json')).read_bytes()) for key in ('bookmarks','portal-references')}
    code = """import sys,json
sys.path.insert(0,code_dir)
from adopt_document_library_links import adopt_links
from adopt_document_portal_tokens import adopt_portal_references
from probe_document_library_community import check_matrix
assert env.cr.dbname==target and len(baseline['documents'])==98
first=[adopt_links(env,catalogs['bookmarks']),adopt_portal_references(env,catalogs['portal-references'])]
assert first in ([98,98],[0,0])
assert [adopt_links(env,catalogs['bookmarks']),adopt_portal_references(env,catalogs['portal-references'])]==[0,0]
decisions=check_matrix(env,baseline)
env.cr.commit()
print('STEPS_COMBINED_DOCUMENTS='+json.dumps({'adopted':first,'user_company_scopes':decisions[0],
    'permissions':decisions[1],'documents':len(baseline['documents'])}))
"""
    prefix = f'code_dir={str(work/"code")!r}\ntarget={target!r}\nbaseline={matrix!r}\ncatalogs={catalogs!r}\n'
    initial_log = work/'adoption.log'
    log_path = initial_log if not initial_log.exists() else work/('adoption-'+str(len(list(work.glob('adoption*.log'))))+'.log')
    with log_path.open('xb') as log:
        proc = subprocess.run(command, input=(prefix+code).encode(), stdout=log, stderr=log)
    rows = [line.split('=',1)[1] for line in log_path.read_text(errors='replace').splitlines()
            if line.startswith('STEPS_COMBINED_DOCUMENTS=')]
    require(proc.returncode == 0 and len(rows)==1, 'document-adoption-matrix-incomplete')
    previous = [json.loads(line.split('=',1)[1]) for path in work.glob('adoption*.log')
                for line in path.read_text(errors='replace').splitlines() if line.startswith('STEPS_COMBINED_DOCUMENTS=')]
    require(sum(record['adopted'] == [98,98] for record in previous)==1, 'initial-document-adoption-missing')
    new_fields = ('step_original_url_hash','step_portal_reference_hash','step_portal_reference_prefix',
                  'step_portal_reference_suffix')
    require(original_rows(target,'documents_document', remove=new_fields)==frozen['public_tables']['documents_document'],
            'original-document-columns-changed')
    for table in ('ir_rule','ir_model_access','ir_attachment'):
        require(original_rows(target,table, maximum_id=limits[table])==frozen['public_tables'][table],
                'original-permissions-changed-'+table)
    reference_command = json.loads((CRM/'native/private-args.json').read_bytes())
    require(reference_command[reference_command.index('-d')+1]=='MANAGEMENT_QA_STEPS_CRM_20261126U42C',
            'wrong-private-native-pair')
    proof = {}
    for label, argv in (('native',reference_command),('community',command)):
        code = (f'import sys,json;sys.path.insert(0,{str(work/"code")!r});'
                "from probe_steps_sales_library import read_filed_documents;print('STEPS_DOCUMENT_READS='+json.dumps(read_filed_documents(env)))")
        path = work/(label+'-files.log')
        with path.open('wb') as logs:
            process = subprocess.run(argv,input=code.encode(),stdout=logs,stderr=logs)
        printed = [line.split('=',1)[1] for line in path.read_text(errors='replace').splitlines()
                   if line.startswith('STEPS_DOCUMENT_READS=')]
        require(process.returncode==0 and len(printed)==1,'actual-library-download-incomplete-'+label)
        proof[label] = json.loads(printed[0])
    require(proof['native']==proof['community'],'original-document-downloads-differ')
    result = json.loads(rows[0])
    result['initial_adoption'] = [98,98]
    result.update(installed=len(expected)+len(extensions),source_sql=SQL_SHA,package_sha256=DOCUMENT_SHA,protected_tables=len(protected)+4,
                  original_file_access=proof['native'],schema=schema_check)
    if with_print:
        result['print_sha256'] = COLORS_SHA
    print(json.dumps(result),flush=True)


if __name__ == '__main__':
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--with-print',action='store_true')
    args = parser.parse_args()
    with open(LOCK,'rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        run(with_print=args.with_print)
