"""Unmodified LGPL vendor sources bound to the exact OCA commit/tree/blobs.

The NUMERIC payroll derivation remains a separate 144-file contract. This
proof adds payroll_account and payroll_contract_advantages without derivation.
No database/ORM, executable artifact imports, private providers or EE bodies.
"""
import ast
import base64
from pathlib import Path, PurePosixPath
import re
import subprocess

from build_numeric_input_engine import PIN
from verify_original_contracts_evidence import git_object_oid, parse_git_tree


VERSIONS = {'payroll': '18.0.1.4.0', 'payroll_account': '18.0.1.0.6',
            'payroll_contract_advantages': '18.0.1.0.0'}


def require(value, message):
    if not value:
        raise ValueError(message)


def verify(proof, files):
    require(proof['schema'] == 1 and proof['oca_pin'] == PIN and proof['modules'] == sorted(VERSIONS),
        'Exact operational vendor profile/pin required')
    require(isinstance(files, dict) and files and all(isinstance(body, bytes) for body in files.values()), 'Vendor source bodies missing')
    require({name.split('/')[0] for name in files} == set(VERSIONS), 'Vendor module scope differs')
    for module, version in VERSIONS.items():
        name = module + '/__manifest__.py'
        require(name in files, 'Vendor manifest missing: ' + module)
        manifest = ast.literal_eval(files[name].decode('utf-8-sig'))
        require(manifest['license'] == 'LGPL-3' and manifest['version'] == version, 'Vendor license/version differs: ' + module)
    def decode(value):
        try:
            return base64.b64decode(value, validate=True)
        except (ValueError, TypeError):
            raise ValueError('Malformed vendor Git object') from None
    commit = decode(proof['commit_object_b64'])
    require(git_object_oid('commit', commit) == PIN, 'Vendor commit is not the pinned OCA commit')
    trees = [line.split(b' ', 1)[1].decode('ascii') for line in commit.split(b'\n\n', 1)[0].splitlines() if line.startswith(b'tree ')]
    require(len(trees) == 1 and re.fullmatch('[0-9a-f]{40}', trees[0]), 'Unique vendor root tree required')
    root = decode(proof['root_tree_object_b64'])
    require(git_object_oid('tree', root) == trees[0], 'Vendor root tree is not in the pinned commit')
    entries = parse_git_tree(root)
    roots = {name: oid for mode, name, oid in entries if name in VERSIONS and mode in (b'40000', b'040000')}
    require(set(roots) == set(VERSIONS), 'A pinned vendor module subtree is missing')
    bodies = {oid: decode(body) for oid, body in proof['trees_by_oid_b64'].items()}
    require(all(re.fullmatch('[0-9a-f]{40}', oid) and git_object_oid('tree', body) == oid
        for oid, body in bodies.items()), 'Vendor tree object hash differs')
    seen, blobs = set(), {}
    def visit(oid, prefix, ancestors=()):
        require(oid in bodies and oid not in ancestors, 'Incomplete/cyclic vendor Git subtree')
        seen.add(oid)
        for mode, name, child in parse_git_tree(bodies[oid]):
            path = prefix + '/' + name
            if mode in (b'40000', b'040000'):
                visit(child, path, ancestors + (oid,))
            else:
                require(path not in blobs and path in files and git_object_oid('blob', files[path]) == child,
                    'Vendor source differs from its exact pinned Git blob: ' + path)
                blobs[path] = child
    for module, oid in roots.items():
        visit(oid, module)
    require(set(blobs) == set(files) and seen == set(bodies), 'Missing/surplus vendor files or Git trees')
    counts = {module: sum(name.startswith(module + '/') for name in files) for module in VERSIONS}
    require(counts['payroll'] == 144, 'Original payroll vendor inventory must remain exactly 144')
    return {'oca_pin': PIN, 'module_files': counts, 'versions': dict(VERSIONS), 'license': 'LGPL-3',
        'all_blobs_bound_to_pinned_commit': True, 'vendor_sources_unmodified': True,
        'extra_derivation': False, 'artifact_code_executed': False}


def capture(oca):
    oca = Path(oca).resolve()
    command = ['git', '-c', 'safe.directory=' + str(oca), '-C', str(oca)]
    def run(*args):
        return subprocess.check_output(command + list(args))
    require(run('rev-parse', 'HEAD').decode().strip() == PIN, 'Vendor checkout pin differs')
    require(not run('status', '--porcelain', '--untracked-files=no').strip(), 'Tracked vendor checkout changed')
    # License gate BEFORE reading any runtime bodies.
    for module, version in VERSIONS.items():
        manifest = ast.literal_eval(run('show', PIN + ':' + module + '/__manifest__.py').decode('utf-8-sig'))
        require(manifest['license'] == 'LGPL-3' and manifest['version'] == version, 'Unreviewed vendor refused')
    files = {}
    for path in filter(None, run('ls-files', '-z', '--', *VERSIONS).decode().split('\0')):
        name = PurePosixPath(path)
        require(not name.is_absolute() and '..' not in name.parts and name.parts[0] in VERSIONS, 'Unsafe vendor path')
        actual = oca / path
        require(actual.is_file() and not actual.is_symlink(), 'Vendor source is not a regular file')
        body = actual.read_bytes()
        require(body == run('show', PIN + ':' + path), 'Vendor worktree differs from pinned Git')
        files[path] = body
    commit = run('cat-file', 'commit', PIN)
    oid = next(line.split(b' ', 1)[1].decode() for line in commit.splitlines() if line.startswith(b'tree '))
    root = run('cat-file', 'tree', oid)
    trees = {}
    def visit(oid):
        if oid in trees:
            return
        body = run('cat-file', 'tree', oid)
        trees[oid] = base64.b64encode(body).decode()
        for mode, name, child in parse_git_tree(body):
            if mode in (b'40000', b'040000'):
                visit(child)
    for mode, name, child in parse_git_tree(root):
        if name in VERSIONS:
            require(mode in (b'40000', b'040000'), 'Vendor root is not a directory')
            visit(child)
    proof = {'schema': 1, 'oca_pin': PIN, 'modules': sorted(VERSIONS),
        'commit_object_b64': base64.b64encode(commit).decode(),
        'root_tree_object_b64': base64.b64encode(root).decode(), 'trees_by_oid_b64': trees}
    verify(proof, files)
    return proof, files
