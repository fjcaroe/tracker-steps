"""Whitelist private NUMERIC/projection evidence, with a full pinned OCA Git proof.

No dump, filestore, credentials or Enterprise runtime bodies are exported.
Snapshots of LGPL/AGPL code are data; the collector executes trusted tools only.
"""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile

from build_original_bootstrap import dependencies, digest, snapshot, hashes
from build_numeric_input_engine import source_files, plan, verify as verify_engine, PIN


def git_proof(oca):
    command = ['git', '-c', 'safe.directory=' + str(oca.resolve()), '-C', str(oca)]
    def raw(kind, oid):
        return subprocess.check_output(command + ['cat-file', kind, oid])
    commit = raw('commit', PIN)
    root_oid = next(line.split(b' ', 1)[1].decode() for line in commit.splitlines() if line.startswith(b'tree '))
    root = raw('tree', root_oid)
    def entries(body):
        offset = 0
        while offset < len(body):
            middle = body.index(b' ', offset); end = body.index(b'\0', middle)
            yield body[offset:middle], body[middle+1:end].decode(), body[end+1:end+21].hex()
            offset = end + 21
        assert offset == len(body)
    payroll = next(oid for mode, name, oid in entries(root) if name == 'payroll' and mode == b'40000')
    trees = {}
    def visit(oid):
        if oid in trees:return
        body = raw('tree', oid); trees[oid] = base64.b64encode(body).decode()
        for mode, name, child in entries(body):
            assert '/' not in name and name not in ('.', '..')
            if mode == b'40000':visit(child)
            else:assert mode in (b'100644', b'100755')
    visit(payroll)
    return {'commit_object_b64': base64.b64encode(commit).decode(),
        'root_tree_object_b64': base64.b64encode(root).decode(), 'trees_by_oid_b64': trees}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root','output','preflight','inventory-root','original-provider','normal-provider','runtime','oca','baseline-archive'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--representation', type=Path)
    args = parser.parse_args()
    assert os.geteuid() == 0
    root, source = args.root.resolve(), args.root.resolve() / 'addons'
    assert root.is_relative_to(Path('/opt/steps-validation')) and not args.output.exists()
    cold = json.loads((root/'community/passed.json').read_text()); native = json.loads((root/'cerro-reference/passed.json').read_text())
    assert cold['expected_test_count'] == 25 and cold['counts'] == {'installed':94,'enterprise':0} and cold['numeric_input_engine']
    assert native['expected_test_count'] == 294 and native['counts'] == {'installed':391,'enterprise':140}
    assert not cold['original_masters_imported'] and not cold['writes_to_source'] and not native['writes_to_source']
    packets = [json.loads((root/mode/'source-files.json').read_text()) for mode in ('community','cerro-reference')]
    assert packets[0] == packets[1] and len(packets[0]) == 361
    assert all(hashlib.sha256((source/name).read_bytes()).hexdigest() == value for name,value in packets[0].items())
    engine = verify_engine(args.oca, root/'engine-addons')
    original_engine = source_files(args.oca); candidate_engine = plan(original_engine)
    report = json.loads((root/'original-bootstrap-derivation.json').read_text())
    pin = json.loads((source/'tools/community/simpledigital_runtime_source.json').read_text())
    # Check licensing before reading provider bodies.
    import ast
    assert ast.literal_eval((args.original_provider/'__manifest__.py').read_text())['license'] == 'AGPL-3'
    original = {name:(args.original_provider/name).read_bytes() for name in pin['files']}
    assert hashes(original) == pin['files'] == report['source_files']
    normal = snapshot(args.normal_provider); provider = snapshot(source/'l10n_cl_simpledigital_payroll')
    assert hashes(normal) == report['normal_files'] and hashes(provider) == report['profile_files']
    definitions, modules = dependencies([source,args.runtime/'addons',args.runtime/'odoo/addons',args.oca])
    assert modules == report['dependencies']
    files, blobs = {}, {}
    for mode in ('community','cerro-reference'):
        for path in (root/mode).iterdir():
            if path.is_file() and path.suffix in ('.json','.log'):files[mode+'/'+path.name] = path
    for name in ('original-bootstrap-derivation.json','oca-input-numeric-derivation.json'):files[name] = root/name
    blobs['dependency-definitions.json'] = json.dumps({'definitions':definitions,'dependencies':modules,
        'definitions_sha256':digest(definitions),'dependency_hashes_match_derivation':True,'server_metadata_only':True,'bodies_replayed_offline':False},indent=2).encode()
    blobs['engine-git-proof.json'] = json.dumps(git_proof(args.oca),indent=2).encode()
    for folder, mapping in (('original-provider',original),('normal-provider',normal),('provider',provider),
                            ('engine-original/payroll',original_engine),('engine-candidate/payroll',candidate_engine)):
        for name, body in mapping.items():blobs[folder+'/'+name] = body
    assert hashlib.sha256(args.baseline_archive.read_bytes()).hexdigest() == '89a6a6762614c1d9a606172bee96a676d08a8117b75456b68c4ff10ae4891e14'
    with tarfile.open(args.baseline_archive) as previous:
        for origin, destination in (('community/passed.json','passed.json'),('community/source-files.json','source-files.json'),('summary-final.json','summary.json')):
            blobs['baseline-F/'+destination] = previous.extractfile(origin).read()
        for member in previous.getmembers():
            if member.isfile() and member.name.startswith('configuration-storage/') and not member.name.endswith('/community-current-contract.json'):
                blobs[member.name] = previous.extractfile(member).read()
    required = {'before.json','after.json','security-admission.json','native-source.json','native-xmlid-classification.json',
        'community-current-contract.json','auditor.py','security-auditor.py','native-verifier.py'}
    assert all((args.preflight/name).is_file() and not (args.preflight/name).is_symlink() for name in required)
    for path in args.preflight.iterdir():
        if path.is_file() and path.suffix in ('.json','.py'):
            folder = 'configuration-storage' if path.name == 'community-current-contract.json' else 'configuration-preflight'
            files[folder+'/'+path.name] = path
    inventory = args.inventory_root/'products-inventory.json'
    files['inventory/products-inventory.json'] = inventory
    files['inventory/auditor.py'] = args.inventory_root/'audit_product_frontier.py'
    raw_delta = (args.inventory_root/'inventory-delta.json').read_bytes(); delta = json.loads(raw_delta)
    assert delta['read_only'] and delta['source_bodies_exported'] is False
    assert delta['current_sha256'] == hashlib.sha256(inventory.read_bytes()).hexdigest()
    blobs['inventory/inventory-delta.json'] = json.dumps(dict(delta,current_inventory_sha256=delta['current_sha256'],
        orm_loaded=False,database_writes=False,original_delta_sha256=hashlib.sha256(raw_delta).hexdigest()),indent=2).encode()
    files['inventory/original-delta.json'] = args.inventory_root/'inventory-delta.json'
    for name in ('build_original_bootstrap.py','build_simpledigital_candidate.py','simpledigital_runtime_source.json',
                 'audit_simpledigital_seed_graph.py','validate_original_bootstrap.py','probe_original_bootstrap.py',
                 'validate_payroll_api.py','offline_process.py','hr_consumer_metadata.py','build_numeric_input_engine.py'):
        files['executed-tools/'+name] = source/'tools/community'/name
    if args.representation:
        proof = json.loads(args.representation.read_text())
        assert proof['database'] == native['database'] and proof['read_only'] and not proof['database_writes']
        files['cerro-reference/business-representation-proof.json'] = args.representation
        files['cerro-reference/representation-auditor.py'] = args.representation.parent/'auditor.py'
    files['collector.py'] = Path(__file__)
    assert not set(files) & set(blobs)
    assert all(path.is_file() and not path.is_symlink() for path in files.values())
    with os.fdopen(os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as stream:
        with tarfile.open(fileobj=stream,mode='w:gz') as archive:
            for name,path in sorted(files.items()):
                data=path.read_bytes(); member=tarfile.TarInfo(name);member.size=len(data);member.mode=0o600;archive.addfile(member,io.BytesIO(data))
            for name,data in sorted(blobs.items()):
                member=tarfile.TarInfo(name);member.size=len(data);member.mode=0o600;archive.addfile(member,io.BytesIO(data))
    print('PRIVATE_ORIGINAL_CONTRACTS_EXPORTED',len(files)+len(blobs),'files; pinned engine Git objects included')


if __name__ == '__main__':main()
