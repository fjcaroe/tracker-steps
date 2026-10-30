"""Trusted-code composition: pinned OCA -> NUMERIC -> HR storage -> deletion.

Only the normal 144-file engine is admitted. The unmodified vendor Git proof
remains separate; this receipt binds its bytes to every derived intermediate.
No artifact Python is loaded and no database or Odoo method is executed.
"""
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath

import build_numeric_input_engine as numeric
import derive_original_payroll_storage as storage
import derive_original_history_deletion as deletion


REPORT = 'oca-original-history-engine-derivation.json'
GUARD_FILE = 'step_payroll_oca_api/models/original_history_deletion.py'
GUARD_SHA256 = '12f6c93dea1c0312d8cd31f914ae36403e5d196f81718fd85a99d1534080fb9a'
GUARD_PATHS = (GUARD_FILE, 'step_payroll_oca_api/__manifest__.py',
    'step_payroll_oca_api/__init__.py', 'step_payroll_oca_api/models/__init__.py')
TOOLS = ('build_numeric_input_engine.py', 'derive_original_payroll_storage.py',
    'derive_original_history_deletion.py', 'original_history_engine_contract.py')


def need(value, code):
    if not value:
        raise ValueError('original-history-engine-' + code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def lf(raw):
    return raw.replace(b'\r\n', b'\n')


def inventory(files):
    need(isinstance(files, dict) and len(files) == 144, 'exact-144-module-relative-files-required')
    for name, body in files.items():
        path = PurePosixPath(name)
        need(isinstance(name, str) and not path.is_absolute() and '..' not in path.parts
            and path.parts and '\\' not in name and '__pycache__' not in path.parts and not name.endswith(('.pyc', '.pyo'))
            and name == path.as_posix() and isinstance(body, bytes), 'regular-module-relative-bytes-required')
    return numeric.hashes(files)


def _imported(raw, name):
    tree = ast.parse(raw.decode('utf-8-sig'))
    return any(isinstance(node, ast.ImportFrom) and node.level == 1 and node.module is None
        and any(alias.name == name for alias in node.names) for node in tree.body)


def guard_contract(files):
    """Exact approved own guard plus real manifest/imports, never a marker."""
    need(isinstance(files, dict) and all(name in files and isinstance(files[name], bytes) for name in GUARD_PATHS),
        'actual-api-guard-source-files-required')
    manifest = ast.literal_eval(files['step_payroll_oca_api/__manifest__.py'].decode('utf-8-sig'))
    need(manifest.get('version') == '18.0.1.17.0' and manifest.get('license') == 'LGPL-3', 'api-1-17-free-manifest-required')
    need(_imported(files['step_payroll_oca_api/__init__.py'], 'models')
        and _imported(files['step_payroll_oca_api/models/__init__.py'], 'original_history_deletion'),
        'actual-api-guard-import-chain-required')
    raw = files[GUARD_FILE]
    need(sha(lf(raw)) == GUARD_SHA256, 'approved-ordinary-actor-deletion-guard-required')
    tree = ast.parse(raw.decode('utf-8-sig'))
    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    need(functions == {'_access', '_lock', '_children', '_company', '_admit_original_company_storage'},
        'real-guard-helper-contract-required')
    classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
    need(set(classes) == {'Payslip', 'PayslipRun'}, 'real-deletion-provider-models-required')
    initializers = [node for node in classes['Payslip'].body if isinstance(node, ast.FunctionDef) and node.name == '_auto_init']
    expected_init = ast.parse('''def _auto_init(self):
    _admit_original_company_storage(self.env.cr, self._table)
    return super()._auto_init()
''').body[0]
    need(len(initializers) == 1 and ast.dump(initializers[0], include_attributes=False)
        == ast.dump(expected_init, include_attributes=False), 'company-null-preflight-must-precede-real-auto-init')
    run = classes['PayslipRun']
    unlink = [node for node in run.body if isinstance(node, ast.FunctionDef) and node.name == 'unlink']
    need(len(unlink) == 1, 'real-run-unlink-required')
    calls = [node for node in ast.walk(unlink[0]) if isinstance(node, ast.Call)]
    need(any(isinstance(node.func, ast.Attribute) and node.func.attr == 'sudo'
        and len(node.args) == 1 and isinstance(node.args[0], ast.Constant) and node.args[0].value is False
        for node in calls), 'ordinary-actor-guard-required')
    named = {node.func.id for node in calls if isinstance(node.func, ast.Name)}
    need({'_lock', '_company', '_children', 'assert_mutable'} <= named, 'guard-lock-history-complete-descendants-required')
    unlink_receivers = {node.func.value.id for node in calls if isinstance(node.func, ast.Attribute)
        and node.func.attr == 'unlink' and isinstance(node.func.value, ast.Name)}
    need({'children', 'slips'} <= unlink_receivers and any(isinstance(node.func, ast.Attribute)
        and node.func.attr == 'unlink' and isinstance(node.func.value, ast.Call)
        and isinstance(node.func.value.func, ast.Name) and node.func.value.func.id == 'super' for node in calls),
        'real-child-slip-and-run-unlink-chain-required')
    return {'api_version': manifest['version'], 'approved_guard_file': GUARD_FILE,
        'approved_guard_lf_sha256': GUARD_SHA256,
        'source_files_lf_sha256': {name: sha(lf(files[name])) for name in GUARD_PATHS},
        'actual_import_chain_validated': True, 'ordinary_actor_and_complete_descendant_guard_present': True,
        'company_null_preflight_before_auto_init': True,
        'context_or_marker_authority': False, 'runtime_guard_execution_certified': False}


def protected_ast(files):
    """Methods, imports, defaults and model identities, without evaluation."""
    result = {}
    for name, raw in sorted(files.items()):
        if not name.endswith('.py'):
            continue
        tree = ast.parse(raw.decode('utf-8-sig'))
        nodes = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Import, ast.ImportFrom)):
                nodes.append(ast.dump(node, include_attributes=False))
            elif isinstance(node, ast.keyword) and node.arg == 'default':
                nodes.append(ast.dump(node, include_attributes=False))
            elif isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in
                    {'_name', '_inherit', '_inherits', '_table', '_auto', '_transient'} for target in node.targets):
                nodes.append(ast.dump(node, include_attributes=False))
        result[name] = sha(json.dumps(nodes, separators=(',', ':')).encode())
    return result


def compose(original, schema_plan, guard_source):
    """Pure normal-engine derivation. schema_plan is the sealed JSON bytes."""
    before_hashes = inventory(original)
    need(isinstance(schema_plan, bytes) and sha(schema_plan) == storage.SCHEMA_PLAN_SHA256,
        'sealed-source-schema-plan6977-required')
    plan = json.loads(schema_plan)
    guard = guard_contract(guard_source)  # BEFORE deriving any CASCADE output.
    need(numeric.PIN == deletion.PIN == '4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e', 'single-pinned-lgpl-engine-required')
    intermediate = numeric.plan(original)
    hr, source_contract = storage.plan_storage(intermediate, plan, anchor_properties=False)
    final, deletion_proof = deletion.plan_history_deletion(hr)
    stages = [('numeric-input', original, intermediate, [numeric.FILE]),
        ('original-hr-storage', intermediate, hr, sorted(storage.EDITS)),
        ('original-company-run-deletion', hr, final, [deletion.FILE])]
    receipts = []
    for name, before, after, expected in stages:
        first, last = inventory(before), inventory(after)
        changed = sorted(path for path in first if first[path] != last[path])
        need(changed == sorted(expected), 'unexpected-stage-file-change:' + name)
        receipts.append({'stage': name, 'before_files': first, 'after_files': last,
            'changed_files': changed, 'complete_file_count': 144})
    protected = protected_ast(original)
    need(protected_ast(final) == protected, 'methods-defaults-imports-or-model-identities-changed')
    need(final['__manifest__.py'] == original['__manifest__.py'], 'vendor-manifest-changed')
    deletion_proof = dict(deletion_proof, builder_sha256=sha(lf(Path(deletion.__file__).read_bytes())))
    report = {'schema': 1, 'profile': 'normal-numeric-original-history-storage-composition',
        'oca_pin': numeric.PIN, 'license': 'LGPL-3', 'source_file_count': 144,
        'schema_plan_sha256': storage.SCHEMA_PLAN_SHA256, 'source_review_sha256': storage.REVIEW_SHA256,
        'source_catalog_sha256': storage.CATALOG_SHA256, 'original_source_files': before_hashes,
        'candidate_files': inventory(final), 'stages': receipts,
        'numeric_receipt_describes_intermediate_only': True,
        'field_policy': dict(storage.FIELD_POLICY, **{'hr.payslip.company_id': {'required': True, 'ondelete': 'restrict'},
            'hr.payslip.payslip_run_id': {'ondelete': 'cascade'}, 'hr.payslip.input.amount': {'digits': False}}),
        'source_storage_contract': source_contract, 'deletion_derivation': deletion_proof,
        'actual_api_guard': guard, 'protected_ast_sha256': protected,
        'builder_sources_lf_sha256': {name: sha(lf((Path(__file__).parent / name).read_bytes())) for name in TOOLS},
        'runtime_methods_changed': False, 'defaults_changed': False, 'imports_changed': False,
        'model_identities_changed': False, 'vendor_manifest_changed': False,
        'source_checkout_changed': False, 'database_accessed': False, 'artifact_python_executed': False,
        'historical_rows_rewritten': False, 'paid_payroll_recalculated': False,
        'unmodified_vendor_git_proof_required_separately': True, 'anchored_properties_profile': False,
        'operational_acceptance': False, 'integral_conversion': False, 'deadline_resolved': False}
    return final, report


def verify_snapshots(original, candidate, report, schema_plan, deletioncode):
    expected, rebuilt = compose(original, schema_plan, deletioncode)
    need(inventory(candidate) == inventory(expected), 'final-engine-source-bytes-differ')
    need(report == rebuilt, 'source-chain-receipt-differs-from-trusted-code-replay')
    return {'schema': 1, 'profile': report['profile'], 'oca_pin': numeric.PIN, 'files': 144,
        'stages': [row['stage'] for row in rebuilt['stages']], 'all_stage_hashes_recomputed': True,
        'actual_api_guard_bound_to_source': True, 'artifact_python_executed': False,
        'methods_defaults_imports_and_model_identities_exact': True,
        'vendor_git_proof_verified_by_this_function': False,
        'database_accessed': False, 'operational_acceptance': False, 'integral_conversion': False}


def _snapshot(folder):
    need(folder.is_dir() and not folder.is_symlink(), 'private-engine-directory-required')
    paths = [path for path in folder.rglob('*') if '__pycache__' not in path.parts]
    need(not any(path.is_symlink() for path in paths), 'engine-symlinks-rejected')
    return {path.relative_to(folder).as_posix(): path.read_bytes() for path in paths if path.is_file()}


def apply(oca, engine, schema_plan, guard_source):
    """After NUMERIC build, before first initialization; no existing DB changes.

    guard_source accepts a trusted own-addon root or its four file byte map.
    No anchored/company/properties profile is silently inferred or accepted.
    """
    oca, engine = Path(oca).resolve(), Path(engine).resolve()
    need(engine.is_relative_to(Path('/opt/steps-validation')) and engine != oca,
        'private-derived-engine-required')
    if not isinstance(guard_source, dict):
        root = Path(guard_source).resolve()
        guard_source = {name: (root / (PurePosixPath(name).relative_to('step_payroll_oca_api')
            if root.name == 'step_payroll_oca_api' else PurePosixPath(name))).read_bytes() for name in GUARD_PATHS}
    schema_raw = Path(schema_plan).read_bytes()
    original = numeric.source_files(oca)
    expected_input = numeric.plan(original)
    output = engine / 'payroll'
    need(inventory(_snapshot(output)) == inventory(expected_input), 'exact-numeric-intermediate-required')
    candidate, report = compose(original, schema_raw, guard_source)
    receipt = engine.parent / REPORT
    need(not receipt.exists(), 'new-final-composition-receipt-required')
    for name in candidate:
        if candidate[name] != expected_input[name]:
            (output / name).write_bytes(candidate[name])
    verify_snapshots(original, _snapshot(output), report, schema_raw, guard_source)
    with os.fdopen(os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write('\n')
    return report
