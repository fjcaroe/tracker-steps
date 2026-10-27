"""Read-only installed-edition and dependency inventory; never edits licensing.

Run on the Odoo host with permission to read its config and PostgreSQL metadata.
The output belongs in a private artifact directory, not the public checkout.
Subscription codes, database UUIDs and credentials are not selected or printed.
"""
import argparse
import ast
import configparser
import json
from pathlib import Path
import subprocess


def query(database, sql):
    result = subprocess.run(['sudo', '-u', 'postgres', 'psql', '-v', 'ON_ERROR_STOP=1',
                             '-d', database, '-At', '-c', sql], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def dependency_path(name, nodes, enterprise, visited=None):
    visited = set(visited or ())
    if name in visited:
        return None
    if name in enterprise:
        return [name]
    visited.add(name)
    paths = []
    for dependency in nodes.get(name, {}).get('depends', []):
        path = dependency_path(dependency, nodes, enterprise, visited)
        if path:
            paths.append([name] + path)
    return min(paths, key=lambda path: (len(path), path)) if paths else None


def removal_dependants(name, nodes):
    affected = {name}
    while True:
        expanded = affected | {key for key, node in nodes.items() if set(node['depends']) & affected}
        if expanded == affected:
            return sorted(affected & set(nodes))
        affected = expanded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--database', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    config = configparser.ConfigParser(interpolation=None)
    assert config.read(args.config)
    options = config['options']
    assert options['db_name'] == args.database, 'Explicit database must match the canonical service config'
    repository = Path(__file__).resolve().parents[2]
    assert not (repository / '.git').exists() or not args.output.resolve().is_relative_to(repository), 'Use private artifacts'
    roots = [Path(value.strip()) for value in options['addons_path'].split(',')]
    modules = query(args.database, """
        SELECT coalesce(json_agg(row_to_json(t)), '[]'::json) FROM (
            SELECT m.name, m.latest_version AS version, m.license AS database_license,
                coalesce((SELECT json_agg(d.name ORDER BY d.name)
                          FROM ir_module_module_dependency d WHERE d.module_id=m.id), '[]'::json) AS depends
            FROM ir_module_module m WHERE m.state='installed' ORDER BY m.name
        ) t
    """)
    for module in modules:
        source = next((root / module['name'] for root in roots
                       if (root / module['name'] / '__manifest__.py').exists()), None)
        module['source_available'] = bool(source)
        module['source'] = str(source) if source else None
        module['license'] = module['database_license']
        if source:
            metadata = ast.literal_eval((source / '__manifest__.py').read_text(encoding='utf-8'))
            module['license'] = metadata.get('license', 'LGPL-3')
            module['manifest_depends'] = metadata.get('depends', [])
            module['manifest_version'] = metadata.get('version')
    nodes = {module['name']: module for module in modules}
    enterprise = {name for name, module in nodes.items() if module['license'] == 'OEEL-1'}
    own = {name for name in nodes if name.startswith('step')}
    impacted = []
    for name in sorted(own):
        path = dependency_path(name, nodes, enterprise)
        if path:
            impacted.append({'module': name, 'shortest_declared_dependency': path})
    params = query(args.database, """
        SELECT json_build_object(
            'expiration_date', (SELECT value FROM ir_config_parameter WHERE key='database.expiration_date'),
            'expiration_reason', (SELECT value FROM ir_config_parameter WHERE key='database.expiration_reason'),
            'subscription_code_present', EXISTS(SELECT 1 FROM ir_config_parameter
                WHERE key='database.enterprise_code' AND coalesce(value,'')<>''))
    """)
    result = {'database': args.database, 'read_only': True, 'expiration': params,
        'counts': {'installed': len(modules), 'enterprise': len(enterprise), 'custom_prefix_step': len(own),
                   'custom_depending_enterprise': len(impacted)},
        'missing_sources': sorted(name for name, module in nodes.items() if not module['source_available']),
        'enterprise_modules': sorted(enterprise), 'custom_dependency_paths': impacted,
        'declared_removal_dependants': {name: removal_dependants(name, nodes)
            for name in ('web_enterprise', 'account_reports', 'web_studio', 'l10n_cl_edi', 'hr_payroll')},
        'modules': modules}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print('COMMUNITY_READINESS_AUDIT_OK ' + json.dumps({
        **result['counts'], 'read_only': True, 'missing_sources': result['missing_sources'],
        'expiration_date': params['expiration_date'], 'expiration_reason': params['expiration_reason'],
        'subscription_code_present': params['subscription_code_present']}))


if __name__ == '__main__':
    main()
