"""Verify the 166-provider Steps release as a delta over the sealed 165-provider product."""
import ast
import hashlib
import json
from pathlib import Path
import re
import tarfile

from verify_converted_backup import check, hash_file, read_json
from verify_steps_integrated_backup import verify as verify_parent
from verify_steps_support_backup import compressed, file_archive, strong
from verify_steps_support_portal_http import compare


PARENT_SHA='347f4447e71372c279cdae51c2beb3baeb432dbdb584533818f9afc635eee772'
PAYMENT_SHA='5428545ab11150a070894e1286480597925c2150856c5ba0344499a2b0c97db2'
SOURCE='COMMUNITY_STEPS_CRM_FISCAL_20261127U45F'
FILES={'source.dump','filestore-delta.tar','filestore.json.gz','snapshot.json.gz','sql-objects.json.gz',
       'providers.json','payment-release.tar','functional-evidence.tar'}


def verify(base,h3,parent,folder,sha,destination=None):
    check(hash_file(folder/'checkpoint.json')==sha,'wrong-payments-checkpoint')
    proof=read_json(folder/'checkpoint.json')
    check(proof['source']==SOURCE and proof['parent']==PARENT_SHA and proof['package']==PAYMENT_SHA and
          set(proof['files'])==FILES,'incomplete-payments-checkpoint')
    for name,(size,checksum) in proof['files'].items():
        path=folder/name
        check(path.is_file() and path.stat().st_size==size and hash_file(path)==checksum,'wrong-payments-piece-'+name)
    verify_parent(base,h3,parent,PARENT_SHA,destination)
    providers=read_json(folder/'providers.json')
    check(providers=={**read_json(parent/'providers.json'),'step_payment_in_process':['18.0.1.0.0','LGPL-3']} and
          len(providers)==166,'wrong-166-provider-roster')
    check(hash_file(folder/'payment-release.tar')==PAYMENT_SHA,'wrong-tested-payments-package')
    with tarfile.open(folder/'payment-release.tar') as package:
        check(sorted(package.getnames())==['step_payment_in_process/'+n for n in ('__init__.py','__manifest__.py','account_move.py')]
              and all(m.isfile() for m in package.getmembers()),'wrong-payments-code')
        manifest=ast.literal_eval(package.extractfile('step_payment_in_process/__manifest__.py').read().decode('utf8'))
        check(manifest['version']=='18.0.1.0.0' and manifest['license']=='LGPL-3' and manifest['depends']==['account'],
              'wrong-payments-manifest')
    previous=compressed(parent,'filestore.json.gz')
    final=compressed(folder,'filestore.json.gz')
    changed={k:v for k,v in final.items() if previous.get(k)!=v}
    removed=sorted(previous.keys()-final.keys())
    check(proof['changed_files']==sorted(changed) and proof['removed_files']==removed and strong(final)==proof['tree_sha256'],
          'wrong-payments-filestore-delta')
    if destination:
        for key in set(removed) | (changed.keys() & previous.keys()):
            check(re.fullmatch(r'(?:checklist/)?[0-9a-f]{2}/[0-9a-f]{40}',key) and
                  (destination/key).resolve().is_relative_to(destination.resolve()),'bad-obsolete-parent-object')
            check(hash_file(destination/key)==previous[key][1],'unexpected-parent-file-during-restoration')
            (destination/key).unlink()
    file_archive(folder/'filestore-delta.tar',changed,destination,changed)
    if destination:
        rebuilt={p.relative_to(destination).as_posix():[p.stat().st_size,hash_file(p)] for p in destination.rglob('*') if p.is_file()}
        check(rebuilt==final,'incorrect-complete-restored-filestore')
    snap=compressed(folder,'snapshot.json.gz')
    check(proof['tables']==len(snap['public_tables']) and proof['sequences']==len(snap['sequence_values']) and
          proof['rows']==sum(v[0] for v in snap['public_tables'].values()) and
          compressed(folder,'sql-objects.json.gz')==compressed(parent,'sql-objects.json.gz'),'incorrect-166-snapshot')
    with tarfile.open(folder/'functional-evidence.tar') as bundle:
        contents={}
        for item in bundle:
            check(item.isfile() and Path(item.name).name==item.name and item.name not in contents,'unexpected-fiscal-evidence')
            contents[item.name]=bundle.extractfile(item).read()
        check({k:hashlib.sha256(v).hexdigest() for k,v in contents.items()}==proof['evidence'],'wrong-functional-files')
        business=json.loads(contents['business.json']);support=json.loads(contents['support.json'])
        check(business['providers']==166 and business['database']==SOURCE and business['payment_cycle']['account_payments']==45
              and all(proof['evidence'].get(k)==v for k,v in business['receipts'].items()),'missing-166-business-acceptance')
        original=json.loads(contents['support-original.json'])
        check(support['modules']==166 and support['db']==SOURCE and support['thread']==original['thread'] and
              support['reference_sha256']==proof['evidence']['support-original.json'] and
              compare(original['http'],support['http'],target=SOURCE)==support['verified_http'] and
              proof['evidence']['ticket-orders.json']=='cdf4e5ac4a8849eea4533f4c83932f6c173e9b8d287352f616d6b4548232fc66',
              'missing-166-portal-or-pagination')
        preservation=json.loads(contents['protected-tables.json'])
        check(not preservation['additional'] and sorted(preservation['changed'])==sorted(preservation['initial']),
              'unexpected-historical-tables-after-functional-tests')
    return {'source':SOURCE,'providers':len(providers),'rows':proof['rows'],'tables':proof['tables'],
            'sequences':proof['sequences'],'files':len(final),'sql_objects':len(compressed(folder,'sql-objects.json.gz')),
            'source_sql_sha256':proof['files']['source.dump'][1],'checkpoint_sha256':sha,'changed_files':len(changed),
            'evidence':len(proof['evidence'])}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('base','h3','parent','folder'):
        parser.add_argument(key,type=Path)
    parser.add_argument('--sha256',required=True)
    args=parser.parse_args()
    print(json.dumps(verify(args.base,args.h3,args.parent,args.folder,args.sha256)))
