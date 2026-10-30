"""Read-only version and effective-source parity for explicitly delivered addons.

This never copies databases, metadata or code between the two environments.
Select only the modules included in the delivery; prototypes retain their scope.
"""
import argparse
import configparser
import json
from pathlib import Path
import re
from manage_management import query, tree_hash


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module',action='append',required=True)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    assert all(re.fullmatch('[a-z][a-z0-9_]+',name) for name in args.module)
    registry=json.loads(Path(__file__).with_name('environments.json').read_text())
    proof={}
    for target in ('cerro','qa-cerro'):
        entry=registry['environments'][target];cfg=configparser.ConfigParser(interpolation=None);cfg.read(entry['config'])
        opts=cfg['options'];assert opts['db_name']==entry['database']
        roots=[Path(path.strip()) for path in opts['addons_path'].split(',')]
        proof[target]={}
        for name in sorted(set(args.module)):
            value=query(entry['database'],"SELECT latest_version FROM ir_module_module WHERE name='%s' AND state='installed'"%name)
            assert value,'Module not installed in '+target+': '+name
            source=next((root/name for root in roots if (root/name/'__manifest__.py').is_file()),None)
            assert source,'Effective module source missing: '+target+'/'+name
            proof[target][name]={'version':value,'sha256':tree_hash(source),'source':str(source)}
    for name in proof['cerro']:
        for key in ('version','sha256'):
            assert proof['cerro'][name][key]==proof['qa-cerro'][name][key],key+' differs for '+name
    if args.output:
        args.output.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        args.output.write_text(json.dumps(proof,indent=2))
    print('CERRO_RELEASE_PAIR_OK '+json.dumps(proof))


if __name__=='__main__':main()
