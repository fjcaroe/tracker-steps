"""Prepare the signed Cerro module path and the verified official Python runtime in the existing local QA userspace."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tarfile

from prepare_cerro_wsl_pilots import ROOT,WORK


def content_hash(paths,core=False):
    dig=hashlib.sha256()
    for relative,signature in sorted(paths,key=lambda p:p[0] if core else Path(p[0]).parts):
        name=relative.encode()
        dig.update(len(name).to_bytes(4,'big')+name+bytes.fromhex(signature))
    return dig.hexdigest()


def tree(path,core=False):
    sources=[]
    for file in path.rglob('*'):
        name=file.relative_to(path)
        if '__pycache__' in name.parts or file.suffix=='.pyc' or (core and name.parts[0]=='addons'):
            continue
        if file.is_file():
            sources.append((name.as_posix(),hashlib.sha256(file.read_bytes()).hexdigest()))
    return content_hash(sources,core)


def main(artifacts,provider,expected_core,estimate=False):
    assert os.getuid()==0 and (ROOT/'pg-source-members.json').is_file()
    base=ROOT/'work/sys-fg-code'
    assert tree(base/'odoo',core=True)==expected_core['odoo'] and hashlib.sha256((base/'odoo-bin').read_bytes()).hexdigest()==expected_core['odoo-bin']
    # Normalize the package inventory first and only link to the existing
    # immutable SyS sources where every byte matches Cerro's own provider.
    package=artifacts/'u44m-runtime.tar.gz'
    assert hashlib.sha256(package.read_bytes()).hexdigest()=='f7d04b1ee1e832c6840fbb346d1829ad64416c1fc213cd43a50347c84c242864'
    target=WORK/'source/addons'
    target.mkdir(parents=True,exist_ok=True)
    with tarfile.open(package) as opened:
        manifest=json.loads(opened.extractfile('module-hashes.json').read())
        assert len(manifest)==188
        shared=set()
        for name,record in manifest.items():
            dest=target/name
            candidate=next((p/name for p in [base/'addons',base/'odoo/addons'] if (p/name/'__manifest__.py').is_file()),None)
            if candidate and tree(candidate)==record['sha256']:
                shared.add(name)
                if estimate:
                    continue
                if not dest.exists():
                    dest.symlink_to(os.path.relpath(candidate,dest.parent),target_is_directory=True)
                assert dest.resolve()==candidate.resolve()
        if estimate:
            needed=sum(m.size for m in opened if m.name!='module-hashes.json' and Path(m.name).parts[1] not in shared)
            print(json.dumps(dict(shared=len(shared),new=188-len(shared),bytes=needed),sort_keys=True))
            return
        for member in opened:
            if member.name=='module-hashes.json':
                continue
            parts=Path(member.name).parts
            assert member.isfile() and parts[0]=='addons' and parts[1] in manifest and '..' not in parts
            if (target/parts[1]).is_symlink():
                continue
            path=target.joinpath(*parts[1:])
            path.parent.mkdir(parents=True,exist_ok=True)
            raw=opened.extractfile(member).read()
            if not path.exists():
                path.write_bytes(raw)
                path.chmod(0o644)
            assert hashlib.sha256(path.read_bytes()).digest()==hashlib.sha256(raw).digest()
        for name,record in manifest.items():
            assert tree((target/name).resolve())==record['sha256']
    assert hashlib.sha256(provider.read_bytes()).hexdigest()=='cdba41119f13f2d01457b5e92c2d8ad92b7aa10bab9e5544d658822d351b6d1c'
    with tarfile.open(provider) as archive:
        for member in archive:
            parts=Path(member.name).parts
            assert member.isfile() and parts[0]=='step_cerro_export_payment_concepts' and '..' not in parts
            path=target.joinpath(*parts)
            path.parent.mkdir(exist_ok=True,parents=True)
            path.write_bytes(archive.extractfile(member).read())
            path.chmod(0o644)
    assert tree(target/'step_cerro_export_payment_concepts')=='abf7405ec810d37b28596121fecc667ef968ebe018b4103da6a5e89302a250d9'
    print(json.dumps(dict(modules=188,shared=len(shared),private=188-len(shared),proposed=1,core=expected_core),sort_keys=True))


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--artifacts',type=Path,required=True)
    cli.add_argument('--provider',type=Path,required=True)
    cli.add_argument('--core-receipt',type=Path,required=True)
    cli.add_argument('--estimate', action='store_true')
    args=cli.parse_args()
    main(args.artifacts,args.provider,json.loads(args.core_receipt.read_bytes()),args.estimate)
