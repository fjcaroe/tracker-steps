"""Export whitelisted private acceptance evidence; never copy dumps or OEEL sources."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tarfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--prior-reference', type=Path, required=True)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--capsule', type=Path, required=True)
    parser.add_argument('--capsule-tool', type=Path, required=True)
    args = parser.parse_args()
    assert os.geteuid() == 0
    for path in vars(args).values():
        assert Path('/opt/steps-validation') in path.resolve().parents
    assert not args.output.exists()
    root, source = args.root.resolve(), args.root.resolve() / 'addons'
    files = {}
    packets = []
    for mode in ('community', 'cerro-reference'):
        stage = root / mode
        proof = json.loads((stage / 'passed.json').read_text())
        assert proof['mode'] == mode and proof['custody_grouping'] and not proof['writes_to_source']
        packet = json.loads((stage / 'source-files.json').read_text())
        assert all(hashlib.sha256((source / name).read_bytes()).hexdigest() == digest for name, digest in packet.items())
        packets.append(packet)
        # Only top-level reports/logs; never source.dump, config, data/filestore.
        for path in stage.iterdir():
            if path.is_file() and path.suffix in ('.json', '.log'):
                files[mode + '/' + path.name] = path
        pdfs=stage/'data/payslip-pdf-evidence'
        if pdfs.exists():
            for path in pdfs.iterdir():
                if path.is_file() and path.suffix in ('.json','.pdf'):
                    files[mode+'/payslip-pdf-evidence/'+path.name]=path
        audit = root / 'adoption-registry' / mode
        assert (audit / 'passed.json').is_file()
        for path in audit.iterdir():
            if path.is_file() and path.suffix in ('.json', '.log', '.py'):
                files['adoption-registry/' + mode + '/' + path.name] = path
    assert packets[0] == packets[1]
    for name in ('validate_adoption_registry.py','batch_registry_contract.py',
                 'caf_registry_contract.py','validate_payroll_relation_storage.py'):
        files['adoption-registry/' + ('validator.py' if name=='validate_adoption_registry.py' else name)] = source / 'tools/community' / name
    for name in packets[0]:
        if name.startswith('l10n_cl_simpledigital_payroll/'):
            files['provider/' + name] = source / name
    assert len([name for name in files if name.startswith('provider/')]) == 52
    files['provider-derivation.json'] = root / 'provider-derivation.json'
    files['basis-input.json'] = root / 'basis-input.json'
    files['configuration-inspector.py'] = source / 'tools/community/inspect_payroll_configuration.py'
    files['identity-snapshotter.py'] = source / 'tools/community/validate_agriculture_core.py'
    # The same approved SyS reference is reused, with provenance and documentary
    # proof. New monthly-basis outcomes come from this exact pair's CLI tests.
    prior_names = ('sys-reference.json', 'reference-auditor.py', 'selection-helper.py',
        'basis-auditor.py', 'basis-helper.py', 'basis-probe.py', 'document-comparison.json', 'document-comparator.py')
    for name in prior_names:
        files[name] = args.prior_reference / name
    for path in (args.prior_reference / 'document').iterdir():
        if path.is_file() and path.suffix in ('.json', '.log', '.py', '.pdf'):
            files['document/' + path.name] = path
    files['products-inventory.json'] = args.inventory
    files['products-auditor.py'] = source / 'tools/community/audit_product_frontier.py'
    files['configuration-capsule.json'] = args.capsule
    files['configuration-exporter.py'] = args.capsule_tool
    files['collector.py'] = Path(__file__)
    assert all(path.is_file() and not path.is_symlink() for path in files.values())
    with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
        with tarfile.open(fileobj=stream, mode='w:gz') as archive:
            for name, path in sorted(files.items()):
                archive.add(path, arcname=name, recursive=False)
    print('PRIVATE_ACCEPTANCE_EXPORTED ' + str(len(files)) + ' files; no dumps/filestore/OEEL sources')


if __name__ == '__main__':
    main()
