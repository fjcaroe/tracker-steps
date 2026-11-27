"""Reattach the two original LGPL fiscal providers in a separate restored Steps sales database."""
import ast
import fcntl
import gzip
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
from tempfile import TemporaryDirectory

from complete_converted_filestore import inventory
from custody_sys_previred_filestore import attachments, digest, object_catalog
from prepare_steps_crm_cohort import digest as fingerprint
from restore_converted_sys_cohort import check_modules, full_snapshot, save, verify_same
from restore_native_product_backup import pg, query
from restore_steps_sales_backup import BASE, SPACE
from restore_sys_previred_pair import GIB, LOCK, require


TARGET = 'COMMUNITY_STEPS_CRM_FISCAL_20261127U45F'
SOURCE = 'COMMUNITY_STEPS_CRM_RECOVERY_20261127U44R'
RECOVERY = BASE/('recovery-'+SOURCE.lower())
SEALED = RECOVERY/'sealed'
WORK = BASE/'steps-sales-fiscal-20261127U45F'
SQL_SHA = '602069d8a5a8a43ff2af901f994794189a50c20857c40490d14c4bc7aa9c054b'
CONTRACTS = {
    'l10n_cl': ('18.0.3.1',51,'9d7de7aa6636f7f72a616171412ac0ff53bf7d6ebeab117ff03cb954e978b3b0'),
    'l10n_latam_invoice_document': ('18.0.1.0',25,'c6b2892e5cd07f111cec03798ec3cfca117dd30340d342c28eff72c3c929d2a7'),
}


def exact_free_providers(active, overlay=WORK/'addons'):
    overlay.mkdir(mode=0o755,exist_ok=True)
    overlay.chmod(0o755)
    for name,(version,count,checksum) in CONTRACTS.items():
        original = Path('/opt/odoo18/odoo/addons')/name
        metadata = ast.literal_eval((original/'__manifest__.py').read_text())
        require(metadata['license']=='LGPL-3' and set(metadata['depends'])<=active|CONTRACTS.keys(),'unavailable-fiscal-dependency')
        release = metadata['version']
        require((release if release.startswith('18.0.') else '18.0.'+release)==version,'original-fiscal-version')
        def members(path):
            files={}
            for file in path.rglob('*'):
                if file.is_file() and '__pycache__' not in file.parts and file.suffix not in ('.pyc','.pyo'):
                    require(file.resolve(strict=True)==file,'unexpected-provider-symlink')
                    files[file.relative_to(path).as_posix()]=digest(file)
            return files
        files = members(original)
        require(len(files)==count and fingerprint(files)==checksum,'original-fiscal-code-changed')
        dest = overlay/name
        if not dest.exists():
            with TemporaryDirectory(dir=overlay) as temp:
                stage = Path(temp)/name
                for key in files:
                    output=stage/key
                    output.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(original/key,output)
                    output.chmod(0o644)
                for folder in [stage,*(p for p in stage.rglob('*') if p.is_dir())]:
                    folder.chmod(0o755)
                stage.rename(dest)
        require(members(dest)==files,'private-fiscal-source-differs')
    return overlay


def restore_original():
    require(Path(__file__).resolve().parent==WORK/'code' and WORK.resolve(strict=True)==WORK,'private-fiscal-directory-required')
    require(digest(SEALED/'source.dump')==SQL_SHA and digest(RECOVERY/'custody-manifest.json')==
            'd45baa7b5c4894a31739d395b61a88f9c11a71b3edb54ecf414383b29296d3d9','accepted-sales-and-documents-required')
    frozen=json.loads(gzip.decompress((SEALED/'source-snapshot.json.gz').read_bytes()))
    marker=WORK/'identity.json'
    identity={'source':SOURCE,'target':TARGET,'sql':SQL_SHA,'tablespace':SPACE}
    exists=query('postgres',f"SELECT count(*) FROM pg_database WHERE datname='{TARGET}'")=='1'
    if not marker.exists():
        require(not exists,'new-private-fiscal-copy-required')
        save(marker,identity)
    require(json.loads(marker.read_bytes())==identity,'unrelated-private-copy')
    if not exists:
        volume=Path(query('postgres',f"SELECT pg_tablespace_location(oid) FROM pg_tablespace WHERE spcname='{SPACE}'"))
        size=int(query('postgres',f"SELECT pg_database_size('{SOURCE}')"))
        require(volume.resolve(strict=True).is_relative_to(BASE/'community-payroll-storage-20261028')
                and shutil.disk_usage(volume).free>=5*GIB+size+(SEALED/'filestore.tar').stat().st_size
                and shutil.disk_usage(query('postgres','SHOW data_directory')).free>=5*GIB,'private-fiscal-space-reserve')
        pg('createdb','--template=template0','--owner=odoo','--tablespace='+SPACE,'--encoding=UTF8',
           '--lc-collate=C','--lc-ctype=C.UTF-8',TARGET)
    require(query('postgres',f"""SELECT pg_get_userbyid(datdba)||'/'||spcname FROM pg_database d
            JOIN pg_tablespace s ON d.dattablespace=s.oid WHERE datname='{TARGET}'""")=='odoo/'+SPACE,'incorrect-private-owner')
    if query(TARGET,"SELECT count(*) FROM pg_tables WHERE schemaname='public'")=='0':
        with (SEALED/'source.dump').open('rb') as src,(WORK/'restore.log').open('ab') as log:
            pg('pg_restore','--exit-on-error','--single-transaction','--no-tablespaces','-d',TARGET,stdin=src,stdout=log,stderr=log)
    dest=WORK/'data/filestore'/TARGET
    if not dest.exists():
        verify_same(frozen,full_snapshot(TARGET))
        original=RECOVERY/'data/filestore'/SOURCE
        physical=json.loads((SEALED/'filestore-physical.json').read_bytes())
        catalog=object_catalog(attachments(TARGET,query)['references'])
        require(fingerprint(inventory(original,catalog))==physical['tree_sha256'],'restored-source-filestore-changed')
        dest.parent.mkdir(parents=True,exist_ok=True)
        with TemporaryDirectory(dir=dest.parent) as temp:
            stage=Path(temp)/'files'
            shutil.copytree(original,stage)
            require(fingerprint(inventory(stage,catalog))==physical['tree_sha256'],'copied-fiscal-filestore-changed')
            stage.rename(dest)
        service=pwd.getpwnam('odoo')
        for path in [WORK/'data',*(WORK/'data').rglob('*')]:
            os.chown(path,service.pw_uid,service.pw_gid)
    return frozen


def run():
    frozen=restore_original()
    known=json.loads((SEALED/'effective-providers.json').read_bytes())
    require(len(known)==160,'original-steps-release-required')
    overlay=exact_free_providers(set(known))
    modules=check_modules(TARGET)
    if modules.keys()==known.keys():
        verify_same(frozen,full_snapshot(TARGET))
        # The native rows, fiscal masters and module metadata come from the restored product.
        # Only reattach the original installed versions after verifying their exact source and dependencies.
        pg('psql','-X','-v','ON_ERROR_STOP=1','-d',TARGET,'-c',"""DO $$ BEGIN
           IF current_database()<>'COMMUNITY_STEPS_CRM_FISCAL_20261127U45F' THEN RAISE EXCEPTION 'wrong copy'; END IF;
           UPDATE ir_module_module SET state='installed' WHERE state='uninstalled' AND license='LGPL-3' AND
           ((name='l10n_cl' AND latest_version='18.0.3.1') OR (name='l10n_latam_invoice_document' AND latest_version='18.0.1.0'));
           IF NOT FOUND OR (SELECT count(*) FROM ir_module_module WHERE state='installed')<>162
           THEN RAISE EXCEPTION 'incorrect fiscal providers'; END IF; END $$;""",stdout=subprocess.DEVNULL)
    require(check_modules(TARGET).keys()==known.keys()|CONTRACTS.keys(),'unexpected-active-fiscal-provider')
    core=SEALED/'runtime'
    # The process uses a private network namespace and a separate writable data directory.
    argv=['unshare','--net','--','sh','-ec','ip link set dev lo up; exec "$@"','steps','runuser','-u','odoo','--',
          'env','PYTHONDONTWRITEBYTECODE=1','/usr/bin/python3.10',str(core/'odoo-bin'),'shell','-c','/etc/odoo18.conf',
          '-d',TARGET,'--db-filter=^'+TARGET+'$','--db_host=/var/run/postgresql','--data-dir='+str(WORK/'data'),
          '--addons-path='+','.join(map(str,(overlay,core/'addons',core/'odoo/addons'))),'--no-http','--workers=0',
          '--max-cron-threads=0','--without-demo=all','--stop-after-init','--load=base,web','--logfile='+str(WORK/'data/fiscal.log')]
    save(WORK/'private-args.json',argv)
    code="""import json
from pathlib import Path
from odoo.modules.module import get_module_path
env.cr.rollback()
env.cr.execute('SET TRANSACTION READ ONLY')
assert env.cr.dbname==target and {r.split(':')[0].strip() for r in Path('/proc/net/dev').read_text().splitlines()[2:]}=={'lo'}
for name in names:
 assert Path(get_module_path(name)).resolve(strict=True)==Path(overlay)/name
assert 'l10n_latam_document_type_id' in env['account.move']._fields and 'l10n_latam_document_number' in env['account.move']._fields
print('REATTACHED_FISCAL='+json.dumps(names))
env.cr.rollback()
"""
    with (WORK/'first-boot.log').open('wb') as handle:
        subprocess.run(argv,input=(f'names={sorted(CONTRACTS)!r}\ntarget={TARGET!r}\noverlay={str(overlay)!r}\n'+code).encode(),
                       check=True,stdout=handle,stderr=handle)
    require('REATTACHED_FISCAL=' in (WORK/'first-boot.log').read_text(errors='replace'),'free-fiscal-boot-failed')
    current=full_snapshot(TARGET)
    require(all(frozen[k]==current[k] for k in frozen if k!='public_tables'),'schema-or-sequence-changed')
    require({k for k in frozen['public_tables'] if frozen['public_tables'][k]!=current['public_tables'][k]}=={'ir_module_module'},
            'original-business-rows-changed')
    print(json.dumps({'database':TARGET,'active':162,'source_sql':SQL_SHA,'original_free_providers':CONTRACTS,
                      'preserved_business_tables':len(current['public_tables'])-1}))


if __name__=='__main__':
    os.umask(0o077)
    with open(LOCK,'rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        run()
