"""Fetch and double-check the hashes of a Cerro logical backup, object archive and inventory."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

NAMES=('COMMUNITY_CERRO_BOM_CONTRACTS_20261127U44M','COMMUNITY_CERRO_BOM_CONTRACTS_20261127U44K',
       'COMMUNITY_CERRO_BOM_PRODUCT_20261126U42P')
CODE='/opt/steps-validation/community-cerro-concepts-20261127U45P/code'
PRIOR='/opt/steps-validation/community-cerro-studio-strict-20261126U42C/tools'


def fetch(db,kind,dest):
    dest.mkdir(parents=True,exist_ok=True)
    target=dest/(db+'-'+kind)
    manifest=target.with_suffix('.json')
    if target.exists():
        claim=json.loads(manifest.read_bytes())
        assert claim['database']==db and claim['artifact']==kind
        assert claim['sha256']==hashlib.sha256(target.read_bytes()).hexdigest()
        return claim
    partial=target.with_suffix('.part')
    command=('sudo env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH='+CODE+':'+PRIOR+
             ' /usr/bin/python3.10 '+CODE+'/backup_cerro_catalog_pilots.py '+db+' '+kind)
    with partial.open('xb') as stream:
        result=subprocess.run(['ssh','-o','BatchMode=yes','odoo-new',command],stdout=stream,stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError('Private backup failed: '+result.stderr.decode(errors='replace')[-500:])
    claim=json.loads(result.stderr.decode().splitlines()[-1])
    assert claim['artifact']==kind and claim['database']==db and re.fullmatch('[0-9a-f]{64}',claim['sha256'])
    assert partial.stat().st_size==claim['bytes'] and hashlib.sha256(partial.read_bytes()).hexdigest()==claim['sha256']
    manifest.write_text(json.dumps(claim,sort_keys=True))
    partial.rename(target)
    return claim


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',choices=NAMES,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    for artifact in ('dump','filestore','inventory'):
        print(json.dumps(fetch(args.database,artifact,args.output),sort_keys=True),flush=True)
