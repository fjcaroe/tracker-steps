"""Pack the precise 188 module sources selected in the accepted Cerro registry for private local rehearsal."""
import fcntl
import gzip
import hashlib
import io
import json
import sys
import tarfile

from backup_cerro_catalog_pilots import Sink
from check_cerro_catalog_contracts import DB,PACKET
from check_cerro_combined_budget import BUDGET,PACKAGE
from check_cerro_export_contacts import CONTACTS
from check_cerro_freight_directory import FREIGHT
from check_cerro_studio_strict import RUNTIME,addon_roots,tree_sha,validate_modules
from restore_cerro_studio_strict import module_census,sql

SOURCE='COMMUNITY_CERRO_BOM_CONTRACTS_20261127U44M'


def main():
    with open('/run/lock/steps-environments.lock','rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_SH)
        expected=module_census(SOURCE)
        assert SOURCE==DB and expected['installed']==188 and not any(expected[k] for k in ('enterprise','non_free','pending'))
        roots=[PACKET,CONTACTS,FREIGHT,BUDGET,PACKAGE,*addon_roots(SOURCE)]
        validate_modules(roots,SOURCE)
        installed=sql(SOURCE,"SELECT name FROM ir_module_module WHERE state='installed' ORDER BY name").splitlines()
        manifest={}
        sink=Sink()
        with gzip.GzipFile(fileobj=sink,mode='wb',compresslevel=1,mtime=0) as compressed:
            with tarfile.open(fileobj=compressed,mode='w|') as archive:
                for name in installed:
                    module=next(r/name for r in roots if (r/name/'__manifest__.py').is_file())
                    paths=[p for p in sorted(module.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']
                    manifest[name]={'sha256':tree_sha(module),'files':len(paths),'official':RUNTIME.resolve() in module.resolve().parents}
                    for path in paths:
                        assert path.resolve().is_relative_to(module.resolve())
                        data=path.read_bytes()
                        member=tarfile.TarInfo('addons/'+name+'/'+path.relative_to(module).as_posix())
                        member.size=len(data)
                        member.mode=0o644
                        archive.addfile(member,io.BytesIO(data))
                raw=json.dumps(manifest,sort_keys=True).encode()
                entry=tarfile.TarInfo('module-hashes.json')
                entry.size=len(raw)
                archive.addfile(entry,io.BytesIO(raw))
        sys.stdout.buffer.flush()
        print(json.dumps(dict(modules=len(manifest),official=sum(s['official'] for s in manifest.values()),
                 bytes=sink.size,sha256=sink.hash.hexdigest(),manifest=hashlib.sha256(raw).hexdigest())),file=sys.stderr)


if __name__=='__main__':
    main()
