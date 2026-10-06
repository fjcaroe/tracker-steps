"""Read-only checks: Demo-SYS may receive only modules already installed in SyS."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import tarfile


def query(database, sql):
    # Linux-only database transport is not needed for pure policy checks.
    from manage_management import query as execute_query
    return execute_query(database, sql)


def check_modules(candidates, reference, dependencies=None):
    reference = set(reference)
    pending, checked = set(candidates), set()
    while pending:
        name = pending.pop()
        if name in checked:
            continue
        if name not in reference:
            raise ValueError('Demo-SYS: módulo fuera del alcance instalado de SyS: ' + name)
        checked.add(name)
        pending.update(set((dependencies or {}).get(name, ())) - checked)
    return checked


def reference_modules(registry):
    if registry['policy'].get('mirrors', {}).get('demo-sys') != 'sys':
        raise ValueError('Registro sin la regla vigente Demo-SYS → SyS')
    database = registry['environments']['sys']['database']
    if query(database, "SELECT name FROM ir_module_module WHERE state IN ('to upgrade','to install','to remove')"):
        raise ValueError('SyS tiene cambios de módulos pendientes; no fijar un alcance ambiguo')
    return set(json.loads(query(database, "SELECT json_agg(name ORDER BY name) FROM ir_module_module WHERE state='installed'")))


def reference_roots(registry):
    database = registry['environments']['sys']['database']
    configured = query(database, "SELECT value FROM ir_config_parameter WHERE key='steps.environment.menu_root_xmlids'")
    if configured:
        roots = json.loads(configured)
        if not isinstance(roots, list) or not all(isinstance(root, str) for root in roots):
            raise ValueError('Alcance de menús de SyS inválido')
        return roots
    roots = query(database, """SELECT json_agg(DISTINCT d.module||'.'||d.name)
        FROM ir_ui_menu m JOIN ir_model_data d ON d.model='ir.ui.menu' AND d.res_id=m.id
        JOIN ir_module_module mod ON mod.name=d.module AND mod.state='installed'
        WHERE m.parent_id IS NULL AND m.active""")
    if not roots or roots == 'null':
        raise ValueError('SyS sin raíces identificables; no ampliar menús por suposición')
    return sorted(json.loads(roots))


def check_release(archive, registry):
    allowed = reference_modules(registry)
    with tarfile.open(archive) as package:
        proof = json.loads(package.extractfile('release.json').read())
        candidates = set(proof['versions'])
        # Refuse unrelated addons even if the installer would leave them unused.
        check_modules(candidates, allowed)
        dependencies = {}
        for name in candidates:
            manifest = ast.literal_eval(package.extractfile(name + '/__manifest__.py').read().decode('utf-8'))
            dependencies[name] = manifest.get('depends', [])
        checked = check_modules(candidates, allowed, dependencies)
    return {'reference': 'sys', 'modules': sorted(candidates), 'checked': sorted(checked),
            'reference_digest': hashlib.sha256(json.dumps(sorted(allowed)).encode()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', type=Path)
    args = parser.parse_args()
    registry = json.loads((Path(__file__).parent / 'environments.json').read_text())
    if args.release:
        print('DEMO_SYS_RELEASE_ALLOWED ' + json.dumps(check_release(args.release, registry)))
        return
    reference = reference_modules(registry)
    target = registry['environments']['demo-sys']['database']
    actual = set(json.loads(query(target, "SELECT json_agg(name ORDER BY name) FROM ir_module_module WHERE state='installed'")))
    print('DEMO_SYS_SCOPE_AUDIT ' + json.dumps({'reference': 'sys', 'reference_count': len(reference),
        'installed_count': len(actual), 'extra_installed': sorted(actual - reference),
        'missing_installed': sorted(reference - actual), 'reference_roots': reference_roots(registry)}))


if __name__ == '__main__':
    main()
