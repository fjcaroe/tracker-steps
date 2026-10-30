"""Unmodified AGPL quality provider, bound to the exact public Git objects.

No database, ORM, native source bodies or executable artifact imports. The
runtime and its private proof are created separately with explicit modes.
"""
import argparse
import ast
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess

from verify_original_contracts_evidence import git_object_oid, parse_git_tree


REPOSITORY = 'https://github.com/OCA/manufacture.git'
PIN = '2d6084f553490408f7a341f05ba6ddd6e641a879'
MODULE = 'quality_control_oca'
VERSION = '18.0.1.4.0'
LICENSE = 'AGPL-3'
DEPENDENCIES = ['product']


def require(value, message):
    if not value:
        raise ValueError(message)


def fingerprint(files):
    hashes = {name: hashlib.sha256(body).hexdigest() for name, body in sorted(files.items())}
    seal = hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return hashes, seal


def verify(proof, files):
    require(proof['schema'] == 1 and proof['repository'] == REPOSITORY
        and proof['oca_pin'] == PIN and proof['module'] == MODULE, 'Exact public quality profile required')
    require(proof['version'] == VERSION and proof['license'] == LICENSE
        and proof['dependencies'] == DEPENDENCIES, 'Quality metadata differs')
    require(isinstance(files, dict) and files and all(isinstance(value, bytes) for value in files.values()),
        'Quality source bytes missing')
    for name in files:
        path = PurePosixPath(name)
        require(not path.is_absolute() and '..' not in path.parts and '\\' not in name
            and path.parts[0] == MODULE, 'Unsafe or out-of-scope quality file')
    manifest = ast.literal_eval(files[MODULE + '/__manifest__.py'].decode('utf-8-sig'))
    require(manifest['license'] == LICENSE and manifest['version'] == VERSION
        and manifest['depends'] == DEPENDENCIES, 'Quality license/version/dependencies differ')

    def decode(value):
        try:
            return base64.b64decode(value, validate=True)
        except (ValueError, TypeError):
            raise ValueError('Malformed quality Git object') from None

    commit = decode(proof['commit_object_b64'])
    require(git_object_oid('commit', commit) == PIN, 'Quality commit is not the pinned OCA commit')
    root_ids = [line.split(b' ', 1)[1].decode('ascii')
        for line in commit.split(b'\n\n', 1)[0].splitlines() if line.startswith(b'tree ')]
    require(len(root_ids) == 1 and re.fullmatch('[0-9a-f]{40}', root_ids[0]), 'Unique quality root tree required')
    root = decode(proof['root_tree_object_b64'])
    require(git_object_oid('tree', root) == root_ids[0], 'Quality root tree differs from pinned commit')
    roots = [(mode, oid) for mode, name, oid in parse_git_tree(root) if name == MODULE]
    require(len(roots) == 1 and roots[0][0] in (b'40000', b'040000'), 'Quality module tree missing')
    trees = {oid: decode(body) for oid, body in proof['trees_by_oid_b64'].items()}
    require(all(re.fullmatch('[0-9a-f]{40}', oid) and git_object_oid('tree', body) == oid
        for oid, body in trees.items()), 'Quality tree hash differs')
    seen, expected = set(), {}

    def visit(oid, prefix, ancestors=()):
        require(oid in trees and oid not in ancestors, 'Incomplete or cyclic quality tree')
        seen.add(oid)
        for mode, name, child in parse_git_tree(trees[oid]):
            path = prefix + '/' + name
            require('/' not in name and name not in ('.', '..'), 'Unsafe Git quality entry')
            if mode in (b'40000', b'040000'):
                visit(child, path, ancestors + (oid,))
            else:
                require(mode in (b'100644', b'100755'), 'Quality symlink/submodule is not admitted')
                require(path not in expected and path in files and git_object_oid('blob', files[path]) == child,
                    'Quality source differs from pinned Git: ' + path)
                expected[path] = child

    visit(roots[0][1], MODULE)
    require(set(files) == set(expected) and seen == set(trees), 'Missing or surplus quality files/trees')
    hashes, seal = fingerprint(files)
    require(proof['source_files_sha256'] == hashes and proof['source_files_fingerprint'] == seal,
        'Quality source fingerprint differs')
    require(proof['file_count'] == len(files) and proof['vendor_sources_unmodified'] is True
        and proof['native_identity_converted'] is False and proof['artifact_code_executed'] is False,
        'Quality scope flags differ')
    return {'oca_pin': PIN, 'module': MODULE, 'version': VERSION, 'license': LICENSE,
        'dependencies': DEPENDENCIES, 'file_count': len(files), 'source_files_fingerprint': seal,
        'all_blobs_bound_to_pinned_commit': True, 'vendor_sources_unmodified': True,
        'native_identity_converted': False, 'artifact_code_executed': False}


def capture(source):
    source = Path(source).resolve()
    command = ['git', '-c', 'safe.directory=' + str(source), '-C', str(source)]

    def run(*args):
        return subprocess.check_output(command + list(args))

    require(run('rev-parse', 'HEAD').decode().strip() == PIN, 'Quality checkout pin differs')
    require(run('remote', 'get-url', 'origin').decode().strip().removesuffix('.git') == REPOSITORY.removesuffix('.git'),
        'Quality checkout must be the public OCA repository')
    require(not run('status', '--porcelain', '--untracked-files=all').strip(), 'Quality checkout must be clean')
    # Gate license/version before reading runtime bodies.
    manifest = ast.literal_eval(run('show', PIN + ':' + MODULE + '/__manifest__.py').decode('utf-8-sig'))
    require(manifest['license'] == LICENSE and manifest['version'] == VERSION
        and manifest['depends'] == DEPENDENCIES, 'Unreviewed quality provider refused')
    files = {}
    for name in filter(None, run('ls-tree', '-rz', '--name-only', PIN, '--', MODULE).decode().split('\0')):
        path = PurePosixPath(name)
        require(not path.is_absolute() and '..' not in path.parts and path.parts[0] == MODULE, 'Unsafe quality path')
        actual = source / name
        require(actual.is_file() and not actual.is_symlink(), 'Quality source must be a regular file')
        body = actual.read_bytes()
        require(body == run('show', PIN + ':' + name), 'Quality worktree differs from pinned Git')
        files[name] = body
    commit = run('cat-file', 'commit', PIN)
    root_id = next(line.split(b' ', 1)[1].decode() for line in commit.splitlines() if line.startswith(b'tree '))
    root = run('cat-file', 'tree', root_id)
    trees = {}

    def visit(oid):
        if oid in trees:
            return
        body = run('cat-file', 'tree', oid)
        trees[oid] = base64.b64encode(body).decode()
        for mode, name, child in parse_git_tree(body):
            if mode in (b'40000', b'040000'):
                visit(child)

    for mode, name, oid in parse_git_tree(root):
        if name == MODULE:
            require(mode in (b'40000', b'040000'), 'Quality subtree is not a directory')
            visit(oid)
    hashes, seal = fingerprint(files)
    proof = {'schema': 1, 'repository': REPOSITORY, 'oca_pin': PIN, 'module': MODULE,
        'version': VERSION, 'license': LICENSE, 'dependencies': DEPENDENCIES,
        'commit_object_b64': base64.b64encode(commit).decode(),
        'root_tree_object_b64': base64.b64encode(root).decode(), 'trees_by_oid_b64': trees,
        'source_files_sha256': hashes, 'source_files_fingerprint': seal, 'file_count': len(files),
        'vendor_sources_unmodified': True, 'native_identity_converted': False, 'artifact_code_executed': False}
    verify(proof, files)
    return proof, files


def materialize(source, output, proof_path):
    proof, files = capture(source)
    output, proof_path = Path(output).resolve(), Path(proof_path).resolve()
    require(not output.exists() and output.parent.is_dir() and not proof_path.exists()
        and proof_path.parent.is_dir() and not proof_path.is_relative_to(output),
        'New separate runtime and private proof destinations required')
    output.mkdir(mode=0o755)
    os.chmod(output, 0o755)
    for name, body in sorted(files.items()):
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644), 'wb') as stream:
            stream.write(body)
        os.chmod(path, 0o644)
    for path in output.rglob('*'):
        if path.is_dir():
            os.chmod(path, 0o755)
    actual = {path.relative_to(output).as_posix(): path.read_bytes() for path in output.rglob('*') if path.is_file()}
    result = verify(proof, actual)
    with os.fdopen(os.open(proof_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(proof, stream, indent=2, sort_keys=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--proof', required=True, type=Path)
    arguments = parser.parse_args()
    print(json.dumps(materialize(arguments.source, arguments.output, arguments.proof), sort_keys=True))
