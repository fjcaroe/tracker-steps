"""Build an immutable management release directly from committed Git blobs."""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import xml.etree.ElementTree as ET

MODULES = ('step_management_costs', 'step_management_costs_agriculture',
           'step_management_costs_machinery', 'step_management_costs_tracker',
           'step_agriculture_catalogs', 'step_management_costs_producers')
SUFFIXES = {'.py', '.xml', '.csv', '.js', '.scss', '.css', '.svg', '.png', '.jpg', '.webp', '.avif', '.md', '.rst'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--commit', default='HEAD')
    parser.add_argument('--kind', choices=('management', 'payroll', 'freight', 'export', 'homepage', 'settings', 'producers'), default='management')
    parser.add_argument('--environment', choices=('development', 'demo-sys', 'sys', 'steps', 'cerro'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    assert not args.output.resolve().is_relative_to(root)
    commit = subprocess.check_output(['git', 'rev-parse', args.commit + '^{commit}'], cwd=root, text=True).strip()
    modules = MODULES if args.kind == 'management' else ('step_environment_policy', 'step_payroll_engine_transition', 'step_hr_contract_days', 'step_hr_previred', 'step_hr_previred_simpledigital', 'step_hr_contract_lifecycle', 'step_hr_contract_lifecycle_simpledigital', 'step_hr_remuneration_book', 'step_inventory_packing', 'step_packing_operations', 'step_producer_fruit_flow')
    if args.kind == 'export':
        modules = ('step_export',)
    if args.kind == 'freight':
        modules = ('step_operations_ui', 'step_dispatch_guide')
    if args.kind == 'homepage':
        modules = ('step_demo_homepage',)
    if args.kind == 'producers':
        modules = ('step_producers', 'step_producer_fruit_flow', 'step_export', 'step_producers_integrations')
    if args.kind == 'settings':
        modules = ('step_account_treasury_batch', 'step_dispatch_guide')
    if args.environment == 'demo-sys':
        if args.kind != 'payroll':
            parser.error('Demo-SYS replica SyS; este publicador solo prepara Nómina para ese destino')
        modules = tuple(name for name in modules if name not in (
            'step_inventory_packing', 'step_packing_operations', 'step_producer_fruit_flow'))
    raw = subprocess.check_output(['git', 'archive', '--format=tar', commit, *modules], cwd=root)
    entries = {}
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        for member in archive.getmembers():
            if not member.isfile() or Path(member.name).suffix not in SUFFIXES:
                continue
            data = archive.extractfile(member).read()
            if member.name.endswith('.py'):
                ast.parse(data.decode('utf-8'), member.name)
            elif member.name.endswith(('.xml', '.svg')):
                ET.fromstring(data)
            entries[member.name] = data
    versions = {name: ast.literal_eval(entries[name + '/__manifest__.py'].decode())['version'] for name in modules}
    proof = {'commit': commit, 'versions': versions, 'files': {name: hashlib.sha256(data).hexdigest() for name, data in entries.items()}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(args.output, 'w:gz') as archive:
        for name, data in [*sorted(entries.items()), ('release.json', json.dumps(proof, indent=2).encode())]:
            member = tarfile.TarInfo(name)
            member.size = len(data)
            member.mode = 0o644
            archive.addfile(member, io.BytesIO(data))
    print('MANAGEMENT_RELEASE_OK ' + json.dumps({'commit': commit, 'sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(), 'files': len(entries), 'versions': versions}))


if __name__ == '__main__':
    main()
