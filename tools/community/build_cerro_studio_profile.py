"""Compose the versioned Cerro product overlay with the agricultural and Packing contracts present from first registration."""
import argparse
import io
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import tempfile

from derive_cerro_estimation_profile import derive as estimates
from derive_cerro_packing_profile import derive as packing

MODULES = (
    'step_agriculture_catalogs','step_agriculture_core','step_agriculture_farm_directory',
    'step_agriculture_shared_farms','step_agriculture_species_pallet','step_agriculture_multicompany',
    'step_cerro_bom_company','step_cerro_product_account_views','step_cerro_studio_adoption',
    'step_cerro_studio_agriculture','step_cerro_studio_budgets','step_cerro_studio_companies',
    'step_cerro_studio_exports','step_cerro_studio_farms','step_cerro_studio_packing',
    'step_cerro_studio_process_types','step_cerro_studio_producers','step_cerro_studio_species','step_cerro_studio_transfers',
    'step_management_costs','step_management_costs_agriculture','step_management_costs_producers',
    'step_management_estimation_entry','step_packing','step_packing_operations','step_packing_process_catalog',
    'step_packing_process_category','step_producer_fruit_reports','step_producers','step_species_tariff',
)


def build(source,output):
    with tempfile.TemporaryDirectory() as temporary:
        temp=Path(temporary)
        estimates(source/'step_management_costs',source/'step_management_estimation_entry',temp/'costs')
        packing(source,temp/'fruit')
        modules={m:next(p/m for p in (temp/'costs',temp/'fruit',source) if (p/m/'__manifest__.py').is_file())
                 for m in MODULES}
        manifest={}
        staging=temp/'cerro-product.tar'
        with tarfile.open(staging,'w',format=tarfile.PAX_FORMAT) as archive:
            for name,module in modules.items():
                content={}
                for path in sorted(module.rglob('*')):
                    if not path.is_file() or '__pycache__' in path.parts or path.suffix=='.pyc':
                        continue
                    relative=path.relative_to(module).as_posix()
                    raw=path.read_bytes()
                    if path.suffix.lower() in ('.py','.xml','.csv','.js','.json','.css','.scss','.html','.po','.pot','.md','.rst','.txt','.yml','.yaml','.svg'):
                        raw=raw.replace(b'\r\n',b'\n')
                    content[relative]=hashlib.sha256(raw).hexdigest()
                    info=tarfile.TarInfo(name+'/'+relative)
                    info.mode=0o644
                    info.size=len(raw)
                    archive.addfile(info,io.BytesIO(raw))
                manifest[name]=content
        with output.open('xb') as target,staging.open('rb') as artifact:
            shutil.copyfileobj(artifact,target)
        return {'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'modules':manifest}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,required=True)
    args=parser.parse_args()
    if args.manifest.exists():
        parser.error('Choose a new manifest file')
    result=build(args.source,args.output)
    with args.manifest.open('x',encoding='utf8') as manifest:
        json.dump(result,manifest,sort_keys=True)
