"""Collect a private MF capsule without database access or executable artifacts.

Only accepted full pair metadata/logs, fixture PDFs, free pinned provider/engine
sources and trusted tool snapshots leave the server. No dump/filestore/OEEL.
"""
import argparse
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile

from build_original_bootstrap import snapshot, hashes
from build_numeric_input_engine import source_files, plan, verify as verify_engine
from collect_original_contracts import git_proof
import verify_multifront_evidence as verifier


def collect(root, output, original_provider, oca, inventory_root, *,
            expected_community_installed, expected_native_installed, representation=None):
    root, output = Path(root).resolve(), Path(output)
    source = root / 'addons'
    assert root.is_relative_to(Path('/opt/steps-validation')) and root.name.startswith('community-multifront-')
    assert not output.exists() and all(type(value) is int and value > minimum for value, minimum in
        ((expected_community_installed, 0), (expected_native_installed, 140)))
    graph = {'source': 'independently_measured_by_coordinator',
             'community': {'installed': expected_community_installed, 'enterprise': 0},
             'cerro-reference': {'installed': expected_native_installed, 'enterprise': 140}}
    packets = [json.loads((root / mode / 'source-files.json').read_text()) for mode in verifier.EXPECTED_TESTS]
    assert packets[0] == packets[1] and {name.split('/')[0] for name in packets[0]} == set(verifier.OWN_MODULES) | {'l10n_cl_simpledigital_payroll'}
    assert all(hashlib.sha256((source / name).read_bytes()).hexdigest() == value for name, value in packets[0].items())
    for mode, expected in verifier.EXPECTED_TESTS.items():
        receipt = json.loads((root / mode / 'passed.json').read_text())
        assert receipt['mode'] == mode and receipt['multifront'] is True and receipt['expected_test_count'] == expected
        assert receipt.get('focused_development_pass') is False
        assert receipt['counts'] == graph[mode] and receipt['writes_to_source'] is False
    # License gate before reading any original provider bodies.
    original_provider = Path(original_provider).resolve()
    assert ast.literal_eval((original_provider / '__manifest__.py').read_text(encoding='utf-8-sig'))['license'] == 'AGPL-3'
    assert ast.literal_eval((source / 'l10n_cl_simpledigital_payroll/__manifest__.py').read_text(encoding='utf-8-sig'))['license'] == 'AGPL-3'
    pin = json.loads((source / 'tools/community/simpledigital_runtime_source.json').read_text())
    assert all(not Path(name).is_absolute() and '..' not in Path(name).parts for name in pin['files'])
    assert all((original_provider / name).is_file() and not (original_provider / name).is_symlink() for name in pin['files'])
    original = {name: (original_provider / name).read_bytes() for name in pin['files']}
    assert not any(path.is_symlink() for path in (source / 'l10n_cl_simpledigital_payroll').rglob('*'))
    normal = snapshot(source / 'l10n_cl_simpledigital_payroll')
    assert len(original) == len(normal) == 52 and hashes(original) == pin['files']
    assert normal == verifier.previous.replay_normal_provider(original)
    verify_engine(Path(oca), root / 'engine-addons')
    original_engine = source_files(Path(oca)); candidate_engine = plan(original_engine)
    assert len(original_engine) == len(candidate_engine) == 144
    files, blobs = {}, {}
    for mode in verifier.EXPECTED_TESTS:
        for path in (root / mode).iterdir():
            if path.is_file() and path.suffix in ('.json', '.log'):
                files[mode + '/' + path.name] = path
        pdf = root / mode / 'data/payslip-pdf-evidence'
        if pdf.exists():
            for path in pdf.iterdir():
                assert path.is_file() and not path.is_symlink() and path.suffix in ('.pdf', '.json')
                files[mode + '/payslip-pdf-evidence/' + path.name] = path
    files['oca-input-numeric-derivation.json'] = root / 'oca-input-numeric-derivation.json'
    for folder, mapping in (('original-provider', original), ('normal-provider', normal),
                            ('engine-original/payroll', original_engine), ('engine-candidate/payroll', candidate_engine)):
        for name, body in mapping.items():
            blobs[folder + '/' + name] = body
    for name in verifier.EXECUTED_TOOLS:
        files['executed-tools/' + name] = source / 'tools/community' / name
    inventory_root = Path(inventory_root).resolve()
    files['inventory/products-inventory.json'] = inventory_root / 'products-inventory.json'
    files['inventory/auditor.py'] = source / 'tools/community/audit_product_frontier.py'
    for name in ('products-inventory-final.json', 'inventory-delta.json', 'inventory-provenance-final.json'):
        path = inventory_root / name
        if path.exists():
            files['inventory/' + name] = path
    if representation:
        representation = Path(representation).resolve()
        proof = json.loads(representation.read_text())
        native = json.loads((root / 'cerro-reference/passed.json').read_text())
        assert proof['database'] == native['database'] and proof['read_only'] is True and proof['database_writes'] is False
        assert proof['native_acceptance_sha256'] == hashlib.sha256((root / 'cerro-reference/passed.json').read_bytes()).hexdigest()
        assert proof['expected_multifront_installed'] == expected_native_installed
        files['cerro-reference/business-representation-proof.json'] = representation
        files['cerro-reference/representation-auditor.py'] = representation.parent / 'auditor.py'
    dump = root / 'cerro-reference/source.dump'
    assert dump.is_file() and not dump.is_symlink()
    digest = hashlib.sha256()
    with dump.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    blobs['source-dump.json'] = json.dumps({'sha256': digest.hexdigest(), 'bytes': dump.stat().st_size,
        'dump_exported': False, 'database_accessed_by_collector': False}, indent=2).encode()
    blobs['graph-admission.json'] = json.dumps(graph, indent=2).encode()
    blobs['engine-git-proof.json'] = json.dumps(git_proof(Path(oca)), indent=2).encode()
    files['collector.py'] = Path(__file__)
    assert not set(files) & set(blobs)
    assert all(path.is_file() and not path.is_symlink() for path in files.values())
    bodies = dict(blobs, **{name: path.read_bytes() for name, path in files.items()})
    manifest = {'schema': 1, 'files': {name: hashlib.sha256(body).hexdigest() for name, body in sorted(bodies.items())},
        'database_accessed': False, 'database_writes': False, 'dump_exported': False,
        'enterprise_source_bodies_exported': False}
    bodies['evidence-files.json'] = json.dumps(manifest, indent=2).encode()
    with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
        with tarfile.open(fileobj=stream, mode='w:gz') as archive:
            for name, body in sorted(bodies.items()):
                member = tarfile.TarInfo(name); member.size = len(body); member.mode = 0o600
                archive.addfile(member, io.BytesIO(body))
    return len(bodies)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'output', 'original-provider', 'oca', 'inventory-root'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--representation', type=Path)
    parser.add_argument('--expected-community-installed', type=int, required=True)
    parser.add_argument('--expected-native-installed', type=int, required=True)
    args = parser.parse_args()
    assert os.geteuid() == 0
    count = collect(args.root, args.output, args.original_provider, args.oca, args.inventory_root,
        expected_community_installed=args.expected_community_installed, expected_native_installed=args.expected_native_installed,
        representation=args.representation)
    print('PRIVATE_MULTIFRONT_EXPORTED', count, 'files; no dump or Enterprise bodies')


if __name__ == '__main__':
    main()
