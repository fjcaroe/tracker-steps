"""Compose the open catalog with its two real model providers on historical native Cerro."""
import argparse
import ast
import hashlib
from pathlib import Path
import shutil

CATALOG = 'b1fcae22bf92978d463af8e37cc816ccb5e4425b55b1ce89d9ba1c24ab112bd0'
LEGACY = '6f43141a41d9a1d04a9f885cea76af6fc490d14b5af3df8a2652605cfd86c7f3'
SEASON = '2e622200c2719704ac4ec23ec30ab922d2239e36c8b5b5403933c2b29e5340df'


def derive(catalog, legacy, output):
    for file, digest in ((catalog/'__manifest__.py',CATALOG),(legacy/'__manifest__.py',LEGACY),
                         (legacy/'models/step_temporada.py',SEASON)):
        if hashlib.sha256(file.read_bytes()).hexdigest()!=digest:
            raise ValueError('An original catalog or native HR provider differs from the Cerro source')
    source = (catalog/'__manifest__.py').read_text()
    spec = ast.literal_eval(source)
    old = ast.literal_eval((legacy/'__manifest__.py').read_text())
    assert spec['depends']==['step_agriculture_core'] and old['version']=='18.0.1.4.0'
    assert old['license']==spec['license']=='LGPL-3'
    assert 'step_agriculture_core' not in old['depends']
    shutil.copytree(catalog,output,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    # The historical native Step HR owns step.temporada too. Its declaration
    # must precede the multi-company extension in every complete registry.
    changed=source.replace("'18.0.1.1.0'","'18.0.1.1.1'").replace("['step_agriculture_core']","['step_agriculture_core','step_hr']")
    expected=dict(spec,version='18.0.1.1.1',depends=['step_agriculture_core','step_hr'])
    assert ast.literal_eval(changed)==expected
    (output/'__manifest__.py').write_text(changed)
    return hashlib.sha256(changed.encode()).hexdigest()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ('catalog','legacy','output'):
        parser.add_argument('--'+arg,type=Path,required=True)
    args=parser.parse_args()
    print(derive(args.catalog,args.legacy,args.output))
