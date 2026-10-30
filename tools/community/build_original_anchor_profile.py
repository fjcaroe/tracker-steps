"""Build a private free-engine profile retaining the anchor's original policy.

No database connection. Normal/F/R3 providers are unchanged. This profile omits
upstream seed/security data, whose real original records already exist in the
anchor; it does not grant permissions or implement missing Enterprise APIs.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

import build_numeric_input_engine as numeric
import build_original_bootstrap as cold


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
        assert name in files and not Path(name).is_absolute() and '..' not in Path(name).parts
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


def build(root, runtime, oca, provider):
    root, runtime, oca, provider = map(Path, (root, runtime, oca, provider))
    source = root / 'source'
    assert all((source / name / '__manifest__.py').is_file() for name in OWN)
    engine = root / 'engine-addons'
    numeric.build(oca, engine)
    shutil.copytree(oca / 'payroll_account', engine / 'payroll_account',
        ignore=shutil.ignore_patterns('__pycache__'))
    changes = {}
    for module in ('payroll', 'payroll_account'):
        folder = engine / module
        files = cold.snapshot(folder)
        updated, plan = ui_profile(files['__manifest__.py'], files)
        (folder / '__manifest__.py').write_bytes(updated)
        changes[module] = dict(plan, original_manifest_sha256=sha(files['__manifest__.py']),
            profile_manifest_sha256=sha(updated), original_files=cold.hashes(files),
            profile_files=cold.hashes(cold.snapshot(folder)))
    cold.build(provider, root / 'profile-addons', dependency_roots=[source],
        community_root=runtime, oca_root=oca)
    overlay = root / 'runtime-addons'; overlay.mkdir(mode=0o755)
    for name in OWN:
        target = source / name
        if name == 'step_simpledigital_oca_security':
            target = root / 'owned-profile' / name
            shutil.copytree(source / name, target)
            path = target / '__manifest__.py'; original = path.read_bytes()
            spec = ast.literal_eval(original.decode('utf-8-sig'))
            assert spec['data'] == ['security.xml']
            spec['data'] = []
            path.write_text(repr(spec) + '\n')
            changes[name] = {'omitted_original_policy_file': 'security.xml',
                'original_manifest_sha256': sha(original), 'profile_manifest_sha256': sha(path.read_bytes())}
        (overlay / name).symlink_to(target)
    (overlay / cold.MODULE).symlink_to(root / 'profile-addons' / cold.MODULE)
    proof = {'schema': 1, 'profile': 'original-anchor-policy-preserving',
        'community_pin': cold.PIN_COMMUNITY, 'oca_pin': cold.PIN_OCA,
        'changes': changes, 'own_modules': OWN, 'database_accessed': False,
        'original_security_policy_required': True, 'new_groups_or_memberships_created': False,
        'default_upstream_security_installed': False, 'all_products_operational': False,
        'deadline_resolved': False}
    cold._write_receipt(root / 'anchor-profile.json', proof)
    for folder in (engine, root / 'owned-profile'):
        for path in (folder, *folder.rglob('*')):
            if not path.is_symlink():path.chmod(0o755 if path.is_dir() else 0o644)
    return proof


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'runtime', 'oca', 'provider'):parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    build(args.root, args.runtime, args.oca, args.provider)
    print('PRIVATE_ORIGINAL_ANCHOR_PROFILE_BUILT')
