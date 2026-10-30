"""One observed LGPL Community view-inheritance SELECT, not a CTE allowlist.

The SQL byte hash is from private Target S7 attempt B (no params captured).
Its source is the real Odoo Community4b4e base/website inheritance builder:
https://github.com/odoo/odoo/blob/4b4efe68291d6def5bb7d2e1f2b829e0cda577d4/odoo/addons/base/models/ir_ui_view.py
https://github.com/odoo/odoo/blob/4b4efe68291d6def5bb7d2e1f2b829e0cda577d4/addons/website/models/ir_ui_view.py
Both are LGPL-3, verified byte-for-byte against that Git object. No Enterprise
source, data, model method override, query rewrite or authority marker.
"""
import ast
from functools import lru_cache
import hashlib
from pathlib import Path
import subprocess
import traceback


PIN = '4b4efe68291d6def5bb7d2e1f2b829e0cda577d4'
QUERY_SHA256 = '4c0933676ecffd506072359a1b096fe7cf4e2e5ba0117f7d13fad1385ceedcab'
CAPTURE_SHA256 = '1a9f9d488d02b19c68b1847cacdb8797a807eb866dd12554d8b477896a834fce'
SPECS = {
    'odoo.addons.base.models.ir_ui_view': {
        'relative': 'odoo/addons/base/models/ir_ui_view.py',
        'sha256': 'a5d6aad64f0950292f291248a3ca35e16b0364f7f4dfae956eb151858218227a',
        'methods': {'_get_inheriting_views': '3da24b52c1a15355c9baa6c7aaa4e8cfb252d762029fbfbeedabd9df3721af6d',
            '_get_inheriting_views_domain': '99e530dcf15feb1af8b94086bf9655d20e3b38de6f0466c1f26dc0584fcc240a'}},
    'odoo.addons.website.models.ir_ui_view': {
        'relative': 'addons/website/models/ir_ui_view.py',
        'sha256': '53554a3fcc86741737c580f771855dc92ce73ba0372a942f10001961f794f862',
        'methods': {'_get_inheriting_views': 'e006a4692e50f94afafaf863d2444b1e49af80546d137343742e1ac1d419a81c',
            '_get_inheriting_views_domain': 'dcfe3bff4c2f621f6bda75a9444b68cce8824c6a8c2f03edc393230647a2454b'}},
}

# Exact parameterized code only, with the observed backend website/active
# predicate. The value of the id parameter is never read, logged or rewritten.
QUERY = '\n            WITH RECURSIVE ir_ui_view_inherits AS (\n                SELECT id, inherit_id, priority, mode, model\n                FROM ir_ui_view\n                WHERE id IN %s AND (((FALSE OR "ir_ui_view"."website_id" IS NULL) AND ("ir_ui_view"."active" = TRUE)))\n            UNION\n                SELECT ir_ui_view.id, ir_ui_view.inherit_id, ir_ui_view.priority,\n                       ir_ui_view.mode, ir_ui_view.model\n                FROM ir_ui_view\n                INNER JOIN ir_ui_view_inherits parent ON parent.id = ir_ui_view.inherit_id\n                WHERE coalesce(ir_ui_view.model, \'\') = coalesce(parent.model, \'\')\n                      AND ir_ui_view.mode = \'extension\'\n                      AND (((FALSE OR "ir_ui_view"."website_id" IS NULL) AND ("ir_ui_view"."active" = TRUE)))\n            )\n            SELECT\n                v.id, v.inherit_id, v.mode\n            FROM ir_ui_view_inherits v\n            ORDER BY v.priority, v.id\n        '


class ViewQueryBlocked(ValueError):
    pass


def need(value, code):
    if not value:
        raise ViewQueryBlocked('core-view-query-' + code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def is_exact_query(code):
    return isinstance(code, str) and sha(code.encode()) == QUERY_SHA256 and code == QUERY


@lru_cache(maxsize=4)
def git_origin(root):
    path = Path(root)
    need(path.is_absolute() and (path / '.git').is_dir() and not (path / '.git').is_symlink(),
        'explicit-official-runtime-git-directory-required')
    # Match the already validated loader boundary: Git2.25's ownership
    # backport ignores -c safe.directory during -C discovery as OSodoo. An
    # explicit admitted git-dir/work-tree avoids discovery and global config
    # changes. Optional index refresh locks remain disabled.
    args = ['git', '--no-optional-locks', '-c', 'safe.directory=' + root,
        '--git-dir=' + str(path / '.git'), '--work-tree=' + root]
    try:
        actual = subprocess.check_output(args + ['rev-parse', 'HEAD'], stderr=subprocess.DEVNULL).decode().strip()
    except (OSError, subprocess.CalledProcessError):
        raise ViewQueryBlocked('core-view-query-official-git-origin-unavailable') from None
    need(actual == PIN, 'official-community-pin-differs')
    return actual


@lru_cache(maxsize=8)
def inspect_file(path_string, module, stat_key):
    """Read only the two approved LGPL files, with exact byte/AST pins."""
    spec = SPECS[module]
    path = Path(path_string)
    relative = Path(spec['relative'])
    need(path.is_absolute() and path.parts[-len(relative.parts):] == relative.parts, 'unexpected-core-source-layout')
    raw = path.read_bytes()
    need(sha(raw) == spec['sha256'], 'official-lgpl-file-bytes-differ')
    root = path.parents[len(relative.parts) - 1]
    pin = git_origin(str(root))
    text = raw.decode('utf-8')
    tree = ast.parse(text)
    methods = {}
    for name, expected in spec['methods'].items():
        nodes = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name]
        need(len(nodes) == 1, 'official-method-not-unique')
        actual = sha(ast.get_source_segment(text, nodes[0]).encode())
        need(actual == expected, 'official-method-ast-segment-differs')
        methods[name] = actual
    return {'module': module, 'file': str(path), 'file_sha256': spec['sha256'],
        'runtime_root': str(root), 'runtime_git_pin': pin, 'method_source_sha256': methods}


def bind_origin(frames, inspector=inspect_file):
    """Both official builders must be in the real call stack, not a context."""
    selected = {}
    for frame in frames:
        module = frame['module']
        if module not in SPECS or frame['function'] != '_get_inheriting_views':
            continue
        need(module not in selected, 'duplicate-inheritance-builder-frame')
        path = Path(frame['file']).resolve()
        info = path.stat()
        stat_key = info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns
        selected[module] = inspector(str(path), module, stat_key)
    need(set(selected) == set(SPECS), 'real-base-and-website-builder-frames-required')
    need(len({item['runtime_root'] for item in selected.values()}) == 1,
        'official-builders-from-different-runtimes')
    return {'statement_sha256': QUERY_SHA256, 'observed_capture_sha256': CAPTURE_SHA256,
        'runtime_git_pin': PIN, 'official_builder_sources': list(selected.values()),
        'backend_website_predicate_unchanged': True, 'source_literal_bytes_unchanged': True,
        'metadata_select_only': True, 'sql_parameters_inspected_or_changed': False,
        'generic_with_admitted': False, 'model_methods_replaced': False}


def current_origin():
    # No source lines, frame locals, credentials, recordsets or params read.
    frames = [{'module': frame.f_globals.get('__name__'), 'function': frame.f_code.co_name,
        'file': frame.f_code.co_filename} for frame, line in traceback.walk_stack(None)]
    return bind_origin(frames)
