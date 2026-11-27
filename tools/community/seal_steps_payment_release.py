"""Freeze the actual 166-module private Steps copy after financial, sales, filing and helpdesk acceptance."""
import argparse
import fcntl
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
from tempfile import TemporaryDirectory

from audit_steps_sales_schema import objects
from complete_converted_filestore import inventory
from custody_sys_previred_filestore import attachments, digest, object_catalog
from integrate_steps_payment_support import CORE, PORTAL, PORTAL_SHA, RELEASES, SUPPORT
from recover_steps_fiscal_fields import RECOVERY, SEALED, TARGET, WORK
from restore_converted_sys_cohort import check_modules, full_snapshot, save, verify_same
from restore_native_product_backup import pg, query
from restore_steps_sales_backup import BASE
from restore_sys_previred_pair import GIB, LOCK, require
from seal_converted_runtime import resolve_providers
from verify_converted_sql_schema import schema
from verify_steps_integrated_backup import FISCAL, FISCAL_SHA, OFFICIAL
from verify_steps_payment_release import FILES, PARENT_SHA, PAYMENT_SHA, verify
from verify_steps_support_backup import canonical, compressed, strong


H3=BASE/'steps-sales-support-20261127U44H3/final-checkpoint'
PARENT=BASE/'steps-integrated-20261127U46A/final-checkpoint'
STAGE=WORK/'all-166'


def code(active):
    runtime=SEALED/'runtime'
    argv=json.loads((WORK/'private-args.json').read_bytes())
    roots=[STAGE/'releases'/CORE,STAGE/'releases'/PORTAL_SHA,WORK/'payment-cycle/releases'/PAYMENT_SHA,
           WORK/'releases'/FISCAL_SHA,WORK/'addons',runtime/'addons',runtime/'odoo/addons']
    require(argv[argv.index('-d')+1]==TARGET and '--addons-path='+','.join(map(str,roots)) in argv and
            str(runtime/'odoo-bin') in argv,'different-loaded-steps-runtime')
    mapped=resolve_providers(runtime,roots,WORK/'data',active)
    overrides={SUPPORT:roots[0],PORTAL:roots[1],'step_payment_in_process':roots[2],FISCAL:roots[3],
               **{k:roots[4] for k in OFFICIAL},'base':roots[-1]}
    for name,version in active.items():
        require(mapped[name]==[str(overrides.get(name,roots[5])/name),*version],'incorrect-166-provider-'+name)
    members=json.loads((SEALED/'runtime-members.json').read_bytes())
    require({p.relative_to(runtime).as_posix() for p in runtime.rglob('*') if p.is_file()}==members.keys() and
            all(digest(runtime/n)==v[1] and (runtime/n).stat().st_mode & 0o777==v[2] for n,v in members.items()),
            'incorrect-160-provider-runtime')
    archives={name:item[2] for name,item in RELEASES.items()}
    payment=WORK/'payment-cycle'/(PAYMENT_SHA+'.tar')
    archives.update({FISCAL:WORK/('status-'+FISCAL_SHA+'.tar'),'step_payment_in_process':payment})
    for name,archive in archives.items():
        root=overrides[name]
        expected={SUPPORT:CORE,PORTAL:PORTAL_SHA,FISCAL:FISCAL_SHA,'step_payment_in_process':PAYMENT_SHA}[name]
        require(digest(archive)==expected,'wrong-test-package-'+name)
        with tarfile.open(archive) as package:
            require({p.relative_to(root).as_posix() for p in (root/name).rglob('*') if p.is_file()}==set(package.getnames()) and
                    all(m.isfile() and (root/m.name).resolve(strict=True)==root/m.name and
                        (root/m.name).read_bytes()==package.extractfile(m).read() for m in package),'different-live-package-'+name)
    for name,(_,count,checksum) in OFFICIAL.items():
        root=roots[4]/name
        hashes={p.relative_to(root).as_posix():digest(p) for p in root.rglob('*') if p.is_file()}
        require(len(hashes)==count and strong(hashes)==checksum,'different-official-fiscal-module-'+name)
    return payment


def physical():
    meta=attachments(TARGET,query)
    return inventory(WORK/'data/filestore'/TARGET,object_catalog(meta.pop('references'))),meta


def seal(evidence_sha):
    folder=STAGE/'evidence'
    require(Path(__file__).resolve().parent==WORK/'code' and digest(folder/'manifest.json')==evidence_sha and
            digest(PARENT/'checkpoint.json')==PARENT_SHA,'wrong-private-payment-release')
    evidence=json.loads((folder/'manifest.json').read_bytes())
    require({'business.json','support.json','U46FullFiscal-steps-invoice-text-fiscal.json'}<=evidence.keys() and
            all(Path(n).name==n and n.endswith('.json') and digest(folder/n)==v for n,v in evidence.items()),
            'wrong-payment-acceptance-files')
    final=STAGE/'final-checkpoint'
    if final.is_dir():
        require(json.loads((final/'checkpoint.json').read_bytes())['evidence']==evidence,'alternate-166-acceptance')
        return verify(RECOVERY,H3,PARENT,final,digest(final/'checkpoint.json'))
    require(shutil.disk_usage(WORK).free>5*GIB+int(query('postgres',f"SELECT pg_database_size('{TARGET}')")) and
            query('postgres',f"SELECT count(*) FROM pg_stat_activity WHERE datname='{TARGET}'")== '0',
            'space-or-active-session-on-166')
    active=check_modules(TARGET)
    require(active=={**json.loads((PARENT/'providers.json').read_bytes()),'step_payment_in_process':['18.0.1.0.0','LGPL-3']},
            'incorrect-parent-modules')
    payment=code(active)
    before=full_snapshot(TARGET)
    definitions=objects(TARGET)
    require(definitions==compressed(PARENT,'sql-objects.json.gz'),'unexpected-financial-schema-drift')
    tree,meta=physical()
    old=compressed(PARENT,'filestore.json.gz')
    changed=sorted(k for k,v in tree.items() if old.get(k)!=v)
    roles=json.loads(query(TARGET,"""SELECT json_agg(name ORDER BY name) FROM (SELECT DISTINCT pg_get_userbyid(refobjid) AS name
                    FROM pg_shdepend WHERE dbid=(SELECT oid FROM pg_database WHERE datname=current_database()) AND refclassid='pg_authid'::regclass
                    UNION SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database()) roles"""))
    with TemporaryDirectory(dir=STAGE) as tmp:
        out=Path(tmp)/'checkpoint'
        out.mkdir()
        shutil.copyfile(payment,out/'payment-release.tar')
        with (out/'source.dump').open('xb') as handle:
            pg('pg_dump','-Fc','--no-tablespaces',TARGET,readonly=True,stdout=handle)
        archive_schema=schema(subprocess.check_output(['pg_restore','--schema-only','--no-tablespaces','--file=-',str(out/'source.dump')]))
        check_schema=schema(pg('pg_dump','--schema-only','--no-tablespaces',TARGET,readonly=True,stdout=subprocess.PIPE).stdout)
        require(archive_schema==check_schema,'incorrect-financial-dump-schema')
        for name,values in (('snapshot.json.gz',before),('sql-objects.json.gz',definitions),('filestore.json.gz',tree)):
            (out/name).write_bytes(gzip.compress(canonical(values),mtime=0))
        save(out/'providers.json',active)
        with tarfile.open(out/'filestore-delta.tar','x') as package:
            for n in changed:
                package.add(WORK/'data/filestore'/TARGET/n,arcname=n,recursive=False)
        with tarfile.open(out/'functional-evidence.tar','x') as package:
            for n in sorted(evidence):
                package.add(folder/n,arcname=n,recursive=False)
        verify_same(before,full_snapshot(TARGET))
        require(objects(TARGET)==definitions and physical()==(tree,meta) and check_modules(TARGET)==active,'state-changed-during-seal')
        proof={'parent':PARENT_SHA,'package':PAYMENT_SHA,'source':TARGET,'schema_sha256':check_schema,'required_roles':roles,
               'rows':sum(v[0] for v in before['public_tables'].values()),'tables':len(before['public_tables']),
               'sequences':len(before['sequence_values']),'sql_objects':len(definitions),'tree_sha256':strong(tree),
               'evidence':evidence,'changed_files':changed,'removed_files':sorted(old.keys()-tree.keys()),'attachment_rows':meta,
               'files':{n:[(out/n).stat().st_size,digest(out/n)] for n in FILES}}
        save(out/'checkpoint.json',proof)
        result=verify(RECOVERY,H3,PARENT,out,digest(out/'checkpoint.json'))
        out.rename(final)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-sha256',required=True)
    args=parser.parse_args()
    os.umask(0o077)
    with open(LOCK,'rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        print(json.dumps(seal(args.evidence_sha256)))
