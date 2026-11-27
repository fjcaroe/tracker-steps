"""Rebuild the exact 24-source archive exercised in the fresh 172-module Cerro Community deployment."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import tarfile
import tempfile

from derive_cerro_estimation_profile import derive as estimates
from derive_cerro_packing_profile import derive as packing

RECEIPT=Path(__file__).with_name('cerro_studio_172_receipt.json')


def build(source,output):
    expected=json.loads(RECEIPT.read_text())
    with tempfile.TemporaryDirectory() as directory:
        work=Path(directory)
        estimates(source/'step_management_costs',source/'step_management_estimation_entry',work/'estimates')
        packing(source,work/'packing')
        archive=work/'cerro-combinado-172.tar'
        with tarfile.open(archive,'w',format=tarfile.PAX_FORMAT) as tar:
            for module,required in sorted(expected['module_trees'].items()):
                root=next(p/module for p in (work/'estimates',work/'packing',source) if (p/module/'__manifest__.py').is_file())
                digest=hashlib.sha256()
                for file in sorted(root.rglob('*'),key=lambda f:tuple(f.relative_to(root).parts)):
                    if not file.is_file() or '__pycache__' in file.parts or file.suffix=='.pyc':
                        continue
                    name=file.relative_to(root).as_posix()
                    raw=file.read_bytes()
                    # The sealed source directories contained both Linux and Windows checkouts.
                    # Restore the accepted line endings independently of the local Git settings.
                    if file.suffix!='.png':
                        raw=raw.replace(b'\r\n',b'\n')
                        if name not in expected['lf_source_files'].get(module,()):
                            raw=raw.replace(b'\n',b'\r\n')
                    name_bytes=name.encode()
                    digest.update(len(name_bytes).to_bytes(4,'big')+name_bytes+hashlib.sha256(raw).digest())
                    info=tarfile.TarInfo(module+'/'+name)
                    info.mode=0o644
                    info.size=len(raw)
                    tar.addfile(info,io.BytesIO(raw))
                if digest.hexdigest()!=required:
                    raise ValueError('Source mismatch for the accepted Cerro module '+module)
        result=hashlib.sha256(archive.read_bytes()).hexdigest()
        if result!=expected['archive_sha256']:
            raise ValueError('The rebuilt archive differs from the qualified Cerro candidate')
        with output.open('xb') as target,archive.open('rb') as incoming:
            shutil.copyfileobj(incoming,target)
        return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(build(args.source,args.output))
