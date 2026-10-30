"""Build a private free-engine profile retaining the anchor's original policy.

No database connection. Normal/F/R3 providers are unchanged. This profile omits
upstream seed/security data, whose real original records already exist in the
anchor; it does not grant permissions or implement missing Enterprise APIs.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import xml.etree.ElementTree as ET

import build_numeric_input_engine as numeric
import build_original_bootstrap as cold
from derive_original_anchor_company import apply_original_company_derivation
from derive_original_anchor_properties import apply_original_property_derivation
from derive_original_payroll_storage import apply_anchor_storage_derivation
from derive_original_anchor_history_deletion import apply_anchor_history_deletion


OWN = ('step_payroll_contracts', 'step_payroll_oca_api', 'step_simpledigital_oca_base',
       'step_simpledigital_oca_security', 'step_payroll_original_report')
UI_MODELS = {'ir.ui.view', 'ir.actions.act_window', 'ir.actions.report', 'ir.ui.menu',
             'ir.actions.act_window.view', 'ir.actions.server', 'mail.template', 'report.paperformat'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def ui_profile(manifest, files):
    spec = ast.literal_eval(manifest.decode('utf-8-sig'))
    assert spec.get('license', 'LGPL-3') == 'LGPL-3'
    selected, omitted = [], []
    for name in spec.get('data', []):
        assert (name in files and '\\' not in name and not PurePosixPath(name).is_absolute()
            and not PureWindowsPath(name).drive and '..' not in PurePosixPath(name).parts)
        if name.startswith(('security/', 'data/')):
            omitted.append(name)
            continue
        assert name.endswith('.xml'), 'Unreviewed non-XML runtime data'
        root = ET.fromstring(files[name])
        assert all(node.get('model') in UI_MODELS for node in root.iter('record')), 'Non-UI runtime producer'
        assert not any(node.tag in ('function', 'delete') for node in root.iter()), 'Runtime mutation in UI data'
        selected.append(name)
    assert selected
    spec['data'] = selected
    return (repr(spec) + '\n').encode(), {'kept_ui': selected, 'omitted_seed_and_policy': omitted}


def build(root, runtime, oca, provider, *, original_storage=False, schema_plan=None):
    assert type(original_storage) is bool and ((schema_plan is not None) is original_storage)
    root, runtime, oca, provider = map(Path, (root, runtime, oca, provider))
    source = root / 'source'
    assert all((source / name / '__manifest__.py').is_file() for name in OWN)
    engine = root / 'engine-addons'
    numeric.build(oca, engine)
    company_derivation = apply_original_company_derivation(oca, engine,
        Path('/opt/steps-validation/community-original-config-20261029/configuration-capsule-C.json'))
    shutil.copytree(oca / 'payroll_account', engine / 'payroll_account',
        ignore=shutil.ignore_patterns('__pycache__'))
    property_derivation = apply_original_property_derivation(oca, engine,
        Path('/opt/steps-validation/community-original-config-20261029/configuration-capsule-C.json'))
    if original_storage:
        storage_derivation = apply_anchor_storage_derivation(oca, engine, schema_plan,
            Path('/opt/steps-validation/community-original-config-20261029/configuration-capsule-C.json'))
        history_deletion_derivation = apply_anchor_history_deletion(oca, engine, schema_plan,
            Path('/opt/steps-validation/community-original-config-20261029/configuration-capsule-C.json'),
            source / 'step_payroll_oca_api')
    changes = {}
    for module in ('payroll', 'payroll_account'):
        folder = engine / module
        files = cold.snapshot(folder)
        updated, plan = ui_profile(files['__manifest__.py'], files)
        if module == 'payroll':
            spec=ast.literal_eval(updated.decode('utf-8-sig'))
            assert 'step_payroll_contracts' not in spec['depends']
            spec['depends'].append('step_payroll_contracts')
            updated=(repr(spec)+'\n').encode()
            plan['adapter_loaded_before_first_payroll_view']='step_payroll_contracts'
        (folder / '__manifest__.py').write_bytes(updated)
        changes[module] = dict(plan, original_manifest_sha256=sha(files['__manifest__.py']),
            profile_manifest_sha256=sha(updated), original_files=cold.hashes(files),
            profile_files=cold.hashes(cold.snapshot(folder)))
    cold.build(provider, root / 'profile-addons', dependency_roots=[source],
        community_root=runtime, oca_root=oca)
    overlay = root / 'runtime-addons'; overlay.mkdir(mode=0o755)
    for name in OWN:
        target = source / name
        if name in ('step_simpledigital_oca_security', 'step_payroll_oca_api'):
            target = root / 'owned-profile' / name
            shutil.copytree(source / name, target)
            path = target / '__manifest__.py'; original = path.read_bytes()
            spec = ast.literal_eval(original.decode('utf-8-sig'))
            if name == 'step_simpledigital_oca_security':
                assert spec['data'] == ['security.xml']
                omitted = list(spec['data']); spec['data'] = []
            else:
                omitted=[item for item in spec['data'] if item.startswith('security/')]
                assert omitted == ['security/ir.model.access.csv','security/configuration_scope.xml']
                updated,_ = ui_profile(original,cold.snapshot(target))
                spec = ast.literal_eval(updated.decode('utf-8-sig'))
            path.write_text(repr(spec) + '\n')
            changes[name] = {'omitted_additive_policy_files': omitted,
                'original_manifest_sha256': sha(original), 'profile_manifest_sha256': sha(path.read_bytes())}
        (overlay / name).symlink_to(target)
    (overlay / cold.MODULE).symlink_to(root / 'profile-addons' / cold.MODULE)
    proof = {'schema': 1, 'profile': 'original-anchor-policy-preserving',
        'community_pin': cold.PIN_COMMUNITY, 'oca_pin': cold.PIN_OCA,
        'changes': changes, 'original_global_company_derivation': company_derivation,
        'original_properties_derivation': property_derivation,
        'own_modules': OWN, 'database_accessed': False,
        'original_security_policy_required': True, 'new_groups_or_memberships_created': False,
        'default_upstream_security_installed': False, 'all_products_operational': False,
        'deadline_resolved': False}
    if original_storage:
        proof['original_storage_derivation'] = storage_derivation
        proof['original_history_deletion_derivation'] = history_deletion_derivation
    cold._write_receipt(root / 'anchor-profile.json', proof)
    for folder in (engine, root / 'owned-profile'):
        for path in (folder, *folder.rglob('*')):
            if not path.is_symlink():path.chmod(0o755 if path.is_dir() else 0o644)
    return proof


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'runtime', 'oca', 'provider'):parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--original-storage', action='store_true')
    parser.add_argument('--schema-plan', type=Path)
    args = parser.parse_args()
    build(args.root, args.runtime, args.oca, args.provider,
        original_storage=args.original_storage, schema_plan=args.schema_plan)
    print('PRIVATE_ORIGINAL_ANCHOR_PROFILE_BUILT')
