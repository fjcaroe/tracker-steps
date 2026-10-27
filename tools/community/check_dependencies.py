"""Fail closed on Enterprise or missing dependencies of a proposed Community package.

Uses a private runtime audit for native modules and current repository manifests
for local modules. This checks declared dependencies, not imports or behavior.
"""
import argparse
import ast
import json
from pathlib import Path


def check(names, nodes):
    errors, visited = [], set()

    def visit(name, path):
        if name in path:
            errors.append('cycle: ' + ' -> '.join(path + [name]))
            return
        if name in visited:
            return
        visited.add(name)
        node = nodes.get(name)
        chain = ' -> '.join(path + [name])
        if node is None:
            errors.append('missing manifest: ' + chain)
            return
        if node.get('source_available') is False:
            errors.append('missing source: ' + chain)
        if node.get('license') == 'OEEL-1':
            errors.append('Enterprise: ' + chain)
        if not node.get('installable', True):
            errors.append('not installable: ' + chain)
        for dependency in node.get('depends', []):
            visit(dependency, path + [name])

    for name in names:
        visit(name, [])
    return sorted(visited), errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--repository', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('modules', nargs='+')
    args = parser.parse_args()
    audit = json.loads(args.audit.read_text(encoding='utf-8'))
    nodes = {m['name']: dict(m, depends=m.get('manifest_depends', m['depends'])) for m in audit['modules']}
    for manifest in args.repository.glob('*/__manifest__.py'):
        nodes[manifest.parent.name] = ast.literal_eval(manifest.read_text(encoding='utf-8-sig'))
    closure, errors = check(args.modules, nodes)
    print(json.dumps({'roots': args.modules, 'dependency_count': len(closure),
                      'declared_community_compatible': not errors, 'errors': errors}, indent=2))
    raise SystemExit(bool(errors))


if __name__ == '__main__':
    main()
