"""Inventory the documented legacy Steps Transport source without loading it.

No imports of the audited addon, source copying, database writes, credentials,
private field values or function bodies appear in the output. A missing license
is a provenance gate, not a grant. Explicit OEEL source scanning is rejected.
"""
import argparse
import ast
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess


def inventory(root):
    manifest = ast.literal_eval((root / '__manifest__.py').read_text())
    if manifest.get('license') == 'OEEL-1':
        raise ValueError('OEEL source scan is outside this tool scope')
    report = {
        'scope': 'custom-source-metadata-only-no-source-copy',
        'path': str(root),
        'provenance_verified': False,
        'manifest': {key: manifest.get(key) for key in
                     ('name', 'version', 'license', 'depends', 'author', 'website', 'data')},
        'files': [], 'models': [], 'routes': [], 'call_counts': {},
    }
    for path in sorted(root.rglob('*')):
        if not path.is_file() or '__pycache__' in path.parts or path.suffix not in (
                '.py', '.xml', '.csv', '.md'):
            continue
        raw = path.read_bytes()
        relative = str(path.relative_to(root))
        report['files'].append({'path': relative, 'bytes': len(raw),
                                'sha256': hashlib.sha256(raw).hexdigest()})
        if path.suffix != '.py' or path.name in ('__manifest__.py', '__init__.py'):
            continue
        tree = ast.parse(raw)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                model = {'class': node.name, 'path': relative, 'line': node.lineno,
                         'models': [], 'fields': []}
                for child in node.body:
                    if not isinstance(child, ast.Assign) or len(child.targets) != 1 or not isinstance(
                            child.targets[0], ast.Name):
                        continue
                    name = child.targets[0].id
                    value = child.value
                    if name in ('_name', '_inherit') and isinstance(value, ast.Constant):
                        model['models'].append({'attribute': name, 'model': value.value})
                    if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) and isinstance(
                            value.func.value, ast.Name) and value.func.value.id == 'fields':
                        item = {'name': name, 'type': value.func.attr}
                        if value.func.attr in ('Many2one', 'One2many', 'Many2many') and value.args and isinstance(
                                value.args[0], ast.Constant):
                            item['relation'] = value.args[0].value
                        model['fields'].append(item)
                if model['models']:
                    report['models'].append(model)
            if isinstance(node, ast.FunctionDef):
                for decorator in node.decorator_list:
                    if not (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                            and decorator.func.attr == 'route'):
                        continue
                    route = {'path': relative, 'line': node.lineno, 'method': node.name,
                             'routes': [], 'options': {}}
                    for argument in decorator.args:
                        try:
                            value = ast.literal_eval(argument)
                        except (ValueError, TypeError):
                            continue
                        if isinstance(value, (str, list)):
                            route['routes'].append(value)
                    for keyword in decorator.keywords:
                        if keyword.arg not in ('auth', 'csrf', 'type', 'methods', 'cors'):
                            continue
                        try:
                            route['options'][keyword.arg] = ast.literal_eval(keyword.value)
                        except (ValueError, TypeError):
                            route['options'][keyword.arg] = 'dynamic'
                    report['routes'].append(route)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in (
                    'sudo', 'create', 'write', 'unlink', 'execute'):
                key = node.func.attr
                report['call_counts'][key] = report['call_counts'].get(key, 0) + 1
    with (root / 'security/ir.model.access.csv').open() as stream:
        report['declared_acl'] = list(csv.DictReader(stream))
    result = subprocess.run(['git', '-C', str(root), 'rev-parse', '--show-toplevel'],
                            capture_output=True, text=True)
    report['git_repository'] = result.returncode == 0
    # A containing repository alone would still not prove this directory tracked.
    if result.returncode == 0:
        tracked = subprocess.run(['git', '-C', str(root), 'ls-files', '--', '.'],
                                 capture_output=True, text=True, check=True)
        report['git_tracked_files'] = tracked.stdout.splitlines()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output.resolve()
    checkout = Path(__file__).resolve().parents[2]
    if root.name != 'steps_transport' or not root.is_dir():
        parser.error('Only the documented steps_transport directory is supported')
    if not args.output.is_absolute() or root in output.parents or checkout in output.parents:
        parser.error('Use a private absolute evidence path outside source checkouts')
    report = inventory(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({'evidence': str(output), 'files': len(report['files']),
                      'models': len(report['models']), 'routes': len(report['routes']),
                      'provenance_verified': False}))


if __name__ == '__main__':
    main()
