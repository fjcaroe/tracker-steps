"""Recover the combined Steps sales and document profile in a new private database and verify both boots."""
import fcntl
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import tarfile
from types import SimpleNamespace

from admit_steps_print_profile import RELEASE as PRINT_SHA
from admit_steps_sales_documents import COMBINED, COMBINED_WORK, DOCUMENT_SHA, PACKAGE
from complete_converted_filestore import complete
from custody_sys_previred_filestore import digest
from prepare_steps_crm_cohort import SOURCE_MANIFESTS, digest as manifest_digest
from restore_converted_sys_cohort import restore
from restore_steps_sales_backup import BASE, SEALED, SPACE
from restore_sys_previred_pair import LOCK, require
from verify_converted_backup import package_manifest
from verify_converted_sql_schema import verify
from verify_steps_sale_documents import verify as compare_sales


TARGET = 'COMMUNITY_STEPS_CRM_RECOVERY_20261127U44R'
OUTPUT = BASE/('recovery-'+TARGET.lower())


def release_from_installed_files(folder):
    files = {}
    for path, checksum, overlay, prefix in (
        (PACKAGE, DOCUMENT_SHA, COMBINED_WORK/'package', ''),
        (COMBINED_WORK/'print.tar', PRINT_SHA, COMBINED_WORK/'print-addons', 'addons/'),
    ):
        require(digest(path)==checksum, 'tested-steps-packages-required')
        with tarfile.open(path) as tar:
            for entry in tar:
                if entry.isdir():
                    continue
                rel = Path(entry.name)
                require(not rel.is_absolute() and '..' not in rel.parts and entry.isfile(), 'invalid-steps-release-member')
                name = prefix + rel.as_posix()
                src = overlay/rel
                require(src.resolve(strict=True)==src and name not in files,'duplicate-or-relocated-provider-file')
                with tar.extractfile(entry) as part:
                    contents = part.read()
                require(contents==src.read_bytes(),'installed-source-differs-from-tested-steps-release')
                files[name] = contents
    require(len(files)==23,'complete-steps-extension-release-required')
    members = json.loads((SEALED/'runtime-members.json').read_bytes())
    providers = json.loads((SEALED/'effective-providers.json').read_bytes())
    manifests = {}
    for name in providers:
        paths = [prefix+'/'+name+'/__manifest__.py' for prefix in ('addons','odoo/addons')]
        original, = [members[path] for path in paths if path in members]
        manifests[name] = original[1]
    require(len(manifests)==157 and manifest_digest(manifests)==SOURCE_MANIFESTS,'original-steps-manifests')
    for name, contents in files.items():
        if name.endswith('/__manifest__.py'):
            module = Path(name).parent.name
            require(module not in manifests,'unexpected-replacement-of-a-steps-provider')
            manifests[module] = sha256(contents).hexdigest()
    require(len(manifests)==160 and manifest_digest(manifests)=='48dc4c5ad578767ebdf00a92792555848dd149d0921c4921ca0adcd0a5e00b0b',
            'sealed-original-manifests-and-three-verified-extensions')
    bundle = io.BytesIO()
    with tarfile.open(fileobj=bundle,mode='w') as tar:
        for name, contents in sorted(files.items()):
            entry = tarfile.TarInfo(name)
            entry.mode,entry.size = 0o644,len(contents)
            tar.addfile(entry,io.BytesIO(contents))
    archive = folder/'original-release.tar'
    checks = ''.join(sha256(contents).hexdigest()+'  '+name+'\n' for name,contents in sorted(files.items()))
    for path, data in ((archive,bundle.getvalue()),(folder/'release-files.sha256',checks.encode())):
        if not path.exists():
            with path.open('xb') as handle:
                handle.write(data)
        require(path.read_bytes()==data,'frozen-steps-release-drift')
    return archive


def run():
    code = COMBINED_WORK/'recovery-code'
    evidence = COMBINED_WORK/'acceptance'
    require(Path(__file__).resolve().parent == code and evidence.resolve(strict=True)==evidence,
            'use-qualified-steps-application-directory')
    read = lambda name: json.loads((evidence/name).read_bytes())
    docs = read('documents.json')
    require(docs['schema']['target']==COMBINED and not any(docs['schema']['schema_changes'].values())
            and (docs['installed'],docs['permissions'],docs['initial_adoption'])==(160,686,[98,98])
            and (docs['package_sha256'],docs['print_sha256'])==(DOCUMENT_SHA,PRINT_SHA),'tested-steps-library-required')
    sale = compare_sales(*(read(name) for name in ('native-pdf.json','combined-pdf.json','native-order.json','combined-order.json')))
    require(sale['matching_pages']==4 and read('combined-order.json')['database']==COMBINED,'tested-steps-sales-required')
    links = read('native-external-links.json')
    require(links==read('combined-external-links.json') and links['files']==81 and len(links['scopes'])==2
            and {scope['public'] for scope in links['scopes'].values()}=={False,True}
            and all(scope['responses']=={'404':72,'200':9} for scope in links['scopes'].values()),
            'original-public-and-portal-downloads-required')
    rows = read('original-business-rows.json')
    require(rows['target']==COMBINED and rows['unchanged_tables']+len(rows['changes'])==1112
            and rows['changes']['documents_document']['original']==98
            and all(rows['changes']['documents_document'][key]==0 for key in ('added','removed','changed')),
            'original-documents-and-business-rows-required')
    release = release_from_installed_files(evidence)
    runtime = SEALED/'runtime'
    args = SimpleNamespace(source=COMBINED,target=TARGET,tablespace=SPACE,expected_active=160,output=OUTPUT,
            release=release,release_sha256=digest(release),runtime=runtime,source_data=COMBINED_WORK/'data',
            addons=[COMBINED_WORK/'package/addons',COMBINED_WORK/'print-addons',runtime/'addons',runtime/'odoo/addons'],
            allow_forward_sequences_on_source=False)
    restore(args)
    complete(OUTPUT, COMBINED_WORK/'data/filestore'/COMBINED)
    verify(OUTPUT)
    proof = json.loads((OUTPUT/'restore-proof.json').read_bytes())
    require(proof['checked_boots']==2 and proof['role_probe']['filed_documents']==docs['original_file_access'],
            'restored-document-route-differs-from-the-original')
    manifest = OUTPUT/'custody-manifest.json'
    entries = package_manifest(OUTPUT)
    if not manifest.exists():
        with manifest.open('x') as out:
            json.dump(entries,out,indent=2,sort_keys=True)
    require(json.loads(manifest.read_bytes())==entries,'steps-custody-members-changed')
    print('STEPS_COMBINED_RECOVERY '+json.dumps({'manifest':digest(manifest),'receipt':digest(OUTPUT/'restore-proof.json'),
          'rows':proof['rows'],'tables':proof['counts']['public_tables'],'files':proof['runtime']['files']}),flush=True)


if __name__ == '__main__':
    os.umask(0o077)
    with open(LOCK,'rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        run()
