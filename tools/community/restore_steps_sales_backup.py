"""Restore a new, identified Steps sales application copy from the accepted external-checkpoint archive."""
import gzip
import json
import os
from pathlib import Path
import pwd
import re
import shutil
from tempfile import TemporaryDirectory

from custody_sys_previred_filestore import attachments, digest, object_catalog, restore_objects
from restore_converted_sys_cohort import full_snapshot, verify_same
from restore_native_product_backup import pg, query
from restore_sys_previred_pair import GIB, require

BASE = Path('/opt/steps-validation')
CRM = BASE/'steps-crm-20261126U42'
SEALED = CRM/'recovery-community_steps_crm_recovery_20261127u42t/sealed'
SPACE = 'steps_community_storage_20261028_community'
SQL_SHA = '0d36901de7be4bf0c20e9b5311c101bb564dc445cb0b8d9bce90ccff8cc7f12d'


def restore(work, target, release_sha):
    profile = re.fullmatch(r'COMMUNITY_STEPS_CRM_(DOC|PRINT|SUPPORT)_([A-Z0-9]+)', target)
    require(profile and re.fullmatch('[a-f0-9]{64}', release_sha), 'invalid-steps-profile')
    purpose = {'DOC':'library','PRINT':'print','SUPPORT':'support'}[profile[1]]
    require(work.resolve(strict=True) == work and work == BASE/f'steps-sales-{purpose}-{profile[2]}',
            'isolated-steps-profile-directory-required')
    source = SEALED/'source.dump'
    physical = SEALED/'filestore.tar'
    require(digest(source) == SQL_SHA and digest(physical) ==
            '021e654b359878d30231b502d440cec2d0a08f04542228302fad999dc573a89b', 'wrong-steps-backup')
    marker = work/'database-identity.json'
    exists = query('postgres',f"SELECT count(*) FROM pg_database WHERE datname='{target}'") == '1'
    identity = {'database': target,'sql': SQL_SHA,'release': release_sha,'tablespace': SPACE}
    if not marker.exists():
        require(not exists, 'fresh-database-required')
        with marker.open('x') as handle:
            json.dump(identity, handle)
    require(json.loads(marker.read_bytes()) == identity, 'another-private-target')
    volume = Path(query('postgres',f"SELECT pg_tablespace_location(oid) FROM pg_tablespace WHERE spcname='{SPACE}'"))
    db_bytes = int(query('postgres',"SELECT pg_database_size('COMMUNITY_STEPS_CRM_RECOVERY_20261127U42T')"))
    require(volume.resolve(strict=True).is_relative_to(BASE/'community-payroll-storage-20261028')
            and shutil.disk_usage(volume).free >= 2*GIB + 2*db_bytes + physical.stat().st_size
            and shutil.disk_usage(query('postgres','SHOW data_directory')).free >= 5*GIB, 'space-reserve')
    if not exists:
        pg('createdb','--template=template0','--owner=odoo','--tablespace='+SPACE,'--encoding=UTF8',
           '--lc-collate=C','--lc-ctype=C.UTF-8',target)
    facts = query('postgres',f"""SELECT pg_get_userbyid(datdba)||'/'||spcname FROM pg_database d JOIN
        pg_tablespace t ON t.oid=d.dattablespace WHERE datname='{target}'""")
    require(facts == 'odoo/'+SPACE,'wrong-target-owner-or-volume')
    if query(target,"SELECT count(*) FROM pg_tables WHERE schemaname='public'") == '0':
        with source.open('rb') as src, (work/'restore.log').open('ab') as log:
            pg('pg_restore','--exit-on-error','--single-transaction','--no-tablespaces','--dbname='+target,
               stdin=src,stdout=log,stderr=log)
    frozen = json.loads(gzip.decompress((SEALED/'source-snapshot.json.gz').read_bytes()))
    store = work/'data/filestore'/target
    if not store.exists():
        verify_same(frozen, full_snapshot(target))
        catalog = object_catalog(attachments(target,query)['references'])
        require(len(catalog) == 1744, 'source-file-count')
        store.parent.mkdir(parents=True,exist_ok=True)
        with TemporaryDirectory(dir=store.parent) as temp:
            tree = Path(temp)/'objects'
            tree.mkdir()
            restore_objects(physical,tree,catalog)
            tree.rename(store)
        service = pwd.getpwnam('odoo')
        for p in (work/'data',*(work/'data').rglob('*')):
            os.chown(p,service.pw_uid,service.pw_gid)
    return frozen
