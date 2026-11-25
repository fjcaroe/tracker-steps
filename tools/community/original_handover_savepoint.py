"""Delegate only actual pinned Odoo UUID1 savepoint controls during projection.

LGPL-3 source: Odoo4b4e, odoo/sql_db.py, Savepoint/_FlushingSavepoint.
https://github.com/odoo/odoo/blob/4b4efe68291d6def5bb7d2e1f2b829e0cda577d4/odoo/sql_db.py
Observed S7 E rejected a canonical SAVEPOINT, never a data write. This does
not admit arbitrary quoted identifiers, user names, SQL params or COMMIT.
"""
import ast
from functools import lru_cache
import hashlib
from pathlib import Path
import re
import sys
import traceback

from original_handover_view_query import git_origin, PIN


FILE_SHA256 = '336db1ae7eca70ecda6d49ff3b5eb0b3c1e88ccc35b89680594b2c1fdcf1a13f'
CLASS_HASHES = {'Savepoint': 'ca8f99c1b79937e924092a618dab32b708ec466b4799dc5c3eb04cc97a16509e',
    '_FlushingSavepoint': '4d8a77660905ce10b868964072adabface8b092aa57b8281f2de60ac8f8b4619'}
UUID1 = r'[0-9a-f]{8}-[0-9a-f]{4}-1[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}'
CONTROL = re.compile(r'(SAVEPOINT|ROLLBACK TO SAVEPOINT|RELEASE SAVEPOINT) "(' + UUID1 + r')"\Z')
METHODS = {'SAVEPOINT': '__init__', 'ROLLBACK TO SAVEPOINT': 'rollback', 'RELEASE SAVEPOINT': '_close'}


class SavepointBlocked(ValueError):
    pass


def need(value, code):
    if not value:
        raise SavepointBlocked('core-savepoint-' + code)


def control(code):
    match = CONTROL.fullmatch(code) if isinstance(code, str) else None
    return (match[1], match[2]) if match else None


@lru_cache(maxsize=4)
def inspect_source(path_string, stat_key):
    path = Path(path_string)
    need(path.is_absolute() and path.parts[-2:] == ('odoo', 'sql_db.py'), 'unexpected-source-layout')
    raw = path.read_bytes()
    need(hashlib.sha256(raw).hexdigest() == FILE_SHA256, 'official-lgpl-file-bytes-differ')
    root = path.parents[1]
    need(git_origin(str(root)) == PIN, 'official-runtime-pin-differs')
    text = raw.decode(); tree = ast.parse(text)
    for name, expected in CLASS_HASHES.items():
        nodes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == name]
        need(len(nodes) == 1 and hashlib.sha256(ast.get_source_segment(text, nodes[0]).encode()).hexdigest()
            == expected, 'official-savepoint-class-ast-differs')
    return {'runtime_git_pin': PIN, 'source_file_sha256': FILE_SHA256,
        'savepoint_class_source_sha256': dict(CLASS_HASHES), 'source_file': str(path)}


def current_origin(operation, name, cursor):
    """Bind actual class/method/object/name/cursor; no frame serialization.

    Only the official Savepoint object's name, closed state and cursor identity
    are inspected. No recordset, credentials, frame locals or SQL parameters
    are copied into the proof.
    """
    method_name = METHODS[operation]
    # Passing the current frame is deliberate: walk_stack(None) skips an
    # interpreter-dependent number of callers and can miss __init__ here.
    for frame, line in traceback.walk_stack(sys._getframe()):
        if frame.f_globals.get('__name__') != 'odoo.sql_db' or frame.f_code.co_name != method_name:
            continue
        cls = frame.f_globals.get('Savepoint')
        flushing = frame.f_globals.get('_FlushingSavepoint')
        method = vars(cls).get(method_name) if isinstance(cls, type) else None
        if getattr(method, '__code__', None) is not frame.f_code:
            continue
        instance = frame.f_locals.get('self')
        need(type(instance) in (cls, flushing), 'actual-official-savepoint-object-required')
        need(instance._cr is cursor and instance.name == name and instance.closed is False,
            'savepoint-name-cursor-or-state-differs')
        path = Path(frame.f_code.co_filename).resolve(); stat = path.stat()
        proof = inspect_source(str(path), (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns))
        return dict(proof, actual_core_object=True, same_cursor=True, same_generated_uuid1=True,
            sql_parameters_inspected_or_changed=False, generic_quoted_identifiers_admitted=False,
            transaction_commit_admitted=False)
    raise SavepointBlocked('core-savepoint-actual-official-method-frame-required')
