"""Whitelist a private cold-bootstrap evidence export; no dumps or OEEL files.

Original/normal/cold provider files are the pinned AGPL runtime only. Payroll
source configuration stays private. No artifact Python is executed by export.
"""
import argparse
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile

from build_original_bootstrap import dependencies, digest, hashes, snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'output', 'preflight', 'input-storage', 'inventory-root',
                 'original-provider', 'normal-provider', 'baseline', 'runtime', 'oca'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    assert os.geteuid() == 0
    for path in vars(args).values():
        assert path.resolve().is_relative_to(Path('/opt/steps-validation')) or path == args.original_provider
    root, source = args.root.resolve(), args.root.resolve() / 'addons'
    assert not args.output.exists()
    cold = json.loads((root / 'community/passed.json').read_text())
    native = json.loads((root / 'cerro-reference/passed.json').read_text())
    assert cold['profile'] == 'original-bootstrap-without-salary-seeds'
    assert cold['counts'] == {'installed': 94, 'enterprise': 0} and cold['expected_test_count'] == 12
    assert not cold['operational_package'] and not cold['original_masters_imported']
    assert native['expected_test_count'] == 294 and native['counts']['enterprise'] == 140
    assert not cold['writes_to_source'] and not native['writes_to_source']
    packets = [json.loads((root / mode / 'source-files.json').read_text()) for mode in ('community', 'cerro-reference')]
    assert packets[0] == packets[1]
    assert all(hashlib.sha256((source / name).read_bytes()).hexdigest() == value for name, value in packets[0].items())
    report = json.loads((root / 'original-bootstrap-derivation.json').read_text())
    pin = json.loads((source / 'tools/community/simpledigital_runtime_source.json').read_text())
    # Check the free license and exact whitelist before copying runtime bodies.
    assert ast.literal_eval((args.original_provider / '__manifest__.py').read_text())['license'] == 'AGPL-3'
    original = {name: (args.original_provider / name).read_bytes() for name in pin['files']}
    assert hashes(original) == pin['files'] == report['source_files']
    assert hashes(snapshot(args.normal_provider)) == report['normal_files']
    assert hashes(snapshot(source / 'l10n_cl_simpledigital_payroll')) == report['profile_files']
    definitions, modules = dependencies([source, args.runtime / 'addons', args.runtime / 'odoo/addons', args.oca])
    assert modules == report['dependencies']
    files, blobs = {}, {}
    for mode in ('community', 'cerro-reference'):
        for path in (root / mode).iterdir():
            if path.is_file() and path.suffix in ('.json', '.log'):
                files[mode + '/' + path.name] = path
    files['original-bootstrap-derivation.json'] = root / 'original-bootstrap-derivation.json'
    blobs['dependency-definitions.json'] = json.dumps({'definitions': definitions, 'dependencies': modules,
        'definitions_sha256': digest(definitions), 'dependency_hashes_match_derivation': True, 'bodies_replayed_offline': False,
        'server_metadata_only': True}, indent=2).encode()
    for name, value in original.items(): blobs['original-provider/' + name] = value
    for name, value in snapshot(args.normal_provider).items(): blobs['normal-provider/' + name] = value
    for name, value in snapshot(source / 'l10n_cl_simpledigital_payroll').items(): blobs['provider/' + name] = value
    for name in ('passed', 'source-files'):
        files['baseline/' + name + '.json'] = args.baseline / 'community' / (name + '.json')
    # Readonly preparation proofs from the last accepted block remain useful;
    # only community-current-contract is replaced by the fresh cold reference.
    for path in (args.baseline / 'configuration-storage').iterdir():
        if path.is_file() and path.suffix in ('.json', '.py') and path.name != 'community-current-contract.json':
            files['configuration-storage/' + path.name] = path
    for path in args.preflight.iterdir():
        if path.is_file() and path.suffix in ('.json', '.py'):
            if path.name == 'community-current-contract.json':
                files['configuration-storage/' + path.name] = path
            else:
                files['configuration-preflight/' + path.name] = path
    for path in args.input_storage.iterdir():
        if path.is_file() and path.suffix in ('.json', '.py'):
            files['input-storage/' + path.name] = path
    for name in ('products-inventory.json', 'products-inventory-delta.json', 'products-frontier.json'):
        files['inventory/' + name] = args.inventory_root / name
    files['inventory/auditor.py'] = args.inventory_root / 'source/tools/community/audit_product_frontier.py'
    for name in ('build_original_bootstrap.py', 'build_simpledigital_candidate.py', 'simpledigital_runtime_source.json',
                 'audit_simpledigital_seed_graph.py', 'validate_original_bootstrap.py', 'probe_original_bootstrap.py',
                 'validate_payroll_api.py', 'offline_process.py', 'hr_consumer_metadata.py'):
        files['executed-tools/' + name] = source / 'tools/community' / name
    files['collector.py'] = Path(__file__)
    assert all(path.is_file() and not path.is_symlink() for path in files.values())
    assert not set(files) & set(blobs)
    def private(info):
        info.mode = 0o600
        return info
    with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
        with tarfile.open(fileobj=stream, mode='w:gz') as archive:
            for name, path in sorted(files.items()): archive.add(path, arcname=name, recursive=False, filter=private)
            for name, data in sorted(blobs.items()):
                member = tarfile.TarInfo(name); member.mode = 0o600; member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
    print('PRIVATE_COLD_BOOTSTRAP_EXPORTED', len(files) + len(blobs), 'files; no dump/filestore/OEEL bodies')


if __name__ == '__main__':
    main()
