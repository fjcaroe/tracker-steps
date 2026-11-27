"""Relocate only inactive Cerro rehearsal artifacts, preserving their original pathname and bytes."""
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

BASE=Path('/opt/steps-validation')
DEST=Path('/srv/odoo-data/steps-anchor-validation/cerro-rehearsal-storage-u45p')
FILES=[
    'community-cerro-bom-adopted-20261126U42B/data/filestore/COMMUNITY_CERRO_BOM_ADOPTED_20261126U42B',
    'community-cerro-estimation-20261126U42E/data/filestore/COMMUNITY_CERRO_BOM_ESTIMATE_20261126U42E',
    'community-cerro-studio-product-20261126U42P/data/filestore/COMMUNITY_CERRO_BOM_PRODUCT_20261126U42P',
    'community-cerro-contracts-20261127U44K/data/filestore/COMMUNITY_CERRO_BOM_CONTRACTS_20261127U44K',
    'community-cerro-studio-catalogue-20261126U40B/upgrade-final-v1/ce-before.dump',
    'community-cerro-studio-catalogue-20261126U40B/upgrade-final-v1/native-before.dump',
    'community-cerro-bom-adopted-20261126U42B/source.dump',
    'community-cerro-bom-adopted-20261126U42B/before-combined-packing.dump',
    'community-cerro-studio-product-20261126U42P/source.dump',
]


def fingerprint(path):
    digest=hashlib.sha256()
    size=allocated=count=0
    for node in [path,*sorted(path.rglob('*'))]:
        if node.is_symlink():
            raise ValueError('Unexpected symbolic link inside the material being relocated')
        st=node.stat()
        item=[node.relative_to(path).as_posix(),st.st_uid,st.st_gid,st.st_mode,st.st_mtime_ns]
        if node.is_file():
            item.append(hashlib.sha256(node.read_bytes()).hexdigest())
            count+=1
            size+=st.st_size
        allocated+=st.st_blocks*512
        digest.update(json.dumps(item).encode()+b'\n')
    return dict(sha256=digest.hexdigest(),bytes=size,files=count,allocated=allocated)


def main():
    if not DEST.parent.is_dir() or os.stat(BASE).st_dev==os.stat(DEST.parent).st_dev:
        raise ValueError('Two distinct existing private storage volumes are required')
    with open('/run/lock/steps-environments.lock','rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        DEST.mkdir(mode=0o711,exist_ok=True)
        receipt=DEST/'location-receipt.json'
        record=json.loads(receipt.read_bytes()) if receipt.exists() else {}
        for relative in FILES:
            current=BASE/relative
            target=DEST/relative
            if current.is_symlink():
                assert current.resolve()==target.resolve() and relative in record
                assert fingerprint(target)['sha256']==record[relative]['sha256']
                continue
            source=fingerprint(current)
            # Keep five GiB available for the existing PostgreSQL volume plus a
            # transient margin for service writes while copying each item.
            if shutil.disk_usage(DEST).free-source['allocated'] < 5*1024**3+64*1024**2:
                break
            if current.is_dir():
                active=subprocess.check_output(['runuser','-u','postgres','--','psql','-XAt','-d','postgres','-c',
                    "SELECT count(*) FROM pg_stat_activity WHERE datname='"+current.name+"'"],text=True)
                assert active.strip()=='0'
            for parent in reversed(target.parents):
                if parent!=DEST and DEST in parent.parents:
                    parent.mkdir(mode=0o711,exist_ok=True)
            if current.is_dir():
                target.mkdir(mode=0o700,exist_ok=True)
                subprocess.run(['rsync','-aHAX','--numeric-ids',str(current)+'/',str(target)+'/'],check=True)
            else:
                subprocess.run(['rsync','-aHAX','--numeric-ids',str(current),str(target)],check=True)
            moved=fingerprint(target)
            assert moved['sha256']==source['sha256'] and moved['files']==source['files']
            temp=current.with_name(current.name+'.verified-relocation')
            assert not temp.exists() and not temp.is_symlink() and temp.parent.resolve()==current.parent.resolve()
            temp.symlink_to(target,target_is_directory=target.is_dir())
            libc=ctypes.CDLL(None,use_errno=True)
            if libc.renameat2(-100,os.fsencode(current),-100,os.fsencode(temp),2)!=0:
                raise OSError(ctypes.get_errno(),'Could not exchange verified archive and its pointer')
            assert current.is_symlink() and current.resolve()==target.resolve() and not temp.is_symlink()
            assert fingerprint(temp)['sha256']==source['sha256']
            record[relative]=source
            staging=receipt.with_suffix('.tmp')
            staging.write_text(json.dumps(record,sort_keys=True))
            staging.replace(receipt)
            if temp.is_dir():
                shutil.rmtree(temp)
            else:
                temp.unlink()
        print(json.dumps({'artifacts':len(record),'bytes':sum(v['bytes'] for v in record.values()),
            'source_free_mib':shutil.disk_usage(BASE).free//2**20,'postgres_free_mib':shutil.disk_usage(DEST).free//2**20}))


if __name__=='__main__':
    main()
