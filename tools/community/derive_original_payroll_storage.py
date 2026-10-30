"""Three pinned LGPL field declarations matching original storage at first init.

No database conversion, defaults, methods, imports, models or source checkout
change. Normal NUMERIC and anchored properties are distinct admitted inputs.
An existing JSONB line column is NOT converted back to text by this builder.
"""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path

import build_numeric_input_engine as numeric
import derive_original_anchor_company as company
import derive_original_anchor_properties as properties
import payroll_configuration_adoption_preflight as gate


REPORT = 'oca-original-storage-first-init-derivation.json'
SCHEMA_PLAN_SHA256 = '6977e9427a8324b7191acde81e82f591999965b0926a2783b4d31e74b3680975'
REVIEW_SHA256 = '12f26677c10e6602e7f0c3e0ab4e9e2a27813d0ee697a2c274b22f79d0a432d8'
CATALOG_SHA256 = '0e16916aa1c86a271998a69a8327e22cfa99096b00504f01dccff1091da14a77'
PINNED_SOURCE = {
    'models/hr_contract.py': '06f3c5abd7bdf824947110dfaf929ca710d968335be2c79fa30dd1ea6fb00045',
    'models/hr_payslip_worked_days.py': '4fcb55c9df4e2b2e04730aaf8dec6d6706c655426d7e0e6a3b068ee3165ce777',
    'models/hr_payslip_line.py': '68f23f57b04976099d8f8e0322861e6cd63ebc139eb618d19fcab3ef3916f2c3',
}
ANCHOR_PROPERTY_LINE_SHA256 = 'd6b61a85eee8b32c2c99bca1adb4bcefad5bdb134a4ac38e92d9a9dcec4c5919'
EDITS = {
    'models/hr_contract.py': (b'        required=True, help="Employee\'s working schedule."',
        b'        required=False, ondelete="set null", help="Employee\'s working schedule."'),
    'models/hr_payslip_worked_days.py': (b'    name = fields.Char(string="Description", required=True)',
        b'    name = fields.Char(string="Description", required=False)'),
    'models/hr_payslip_line.py': (b'    _order = "contract_id, sequence"\n',
        b'    _order = "contract_id, sequence"\n\n    name = fields.Char(required=True, translate=False)\n'),
}
FIELD_POLICY = {
    'hr.contract.resource_calendar_id': {'required': False, 'ondelete': 'set null'},
    'hr.payslip.worked_days.name': {'required': False, 'type': 'char'},
    'hr.payslip.line.name': {'required': True, 'type': 'char', 'translate': False},
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def source_storage_contract(plan):
    gate.require(plan.get('schema') == 1 and plan.get('oca_payroll_pin') == numeric.PIN
        and plan.get('review_sha256') == REVIEW_SHA256 and plan.get('catalog_sha256') == CATALOG_SHA256
        and plan.get('analysis_input') == 'existing-private-S7-readonly-artifacts-only'
        and plan.get('database_queries_executed') == 0 and plan.get('database_writes') is False
        and plan.get('acceptance_authorized') is False, 'original-storage-review-provenance-required')
    source_columns = {}
    gate.require(len(plan['not_null_added']) == 2, 'exact-two-original-required-drifts-required')
    for row in plan['not_null_added']:
        before, after = row['before'], row['after']
        key = (before['table_name'], before['column_name'])
        expected_type = {('hr_contract', 'resource_calendar_id'): 'integer',
            ('hr_payslip_worked_days', 'name'): 'character varying'}.get(key)
        gate.require(expected_type and before == dict(table_name=key[0], column_name=key[1],
            sql_type=expected_type, not_null=False, default_md5=None)
            and after == dict(before, not_null=True), 'original-nullable-storage-contract-drift')
        source_columns['.'.join(key)] = before
    gate.require(len(source_columns) == 2 and len(plan['type_changes']) == 1, 'original-three-column-storage-scope-drift')
    before, after = plan['type_changes'][0]['before'], plan['type_changes'][0]['after']
    gate.require(before == {'table_name': 'hr_payslip_line', 'column_name': 'name',
        'sql_type': 'character varying', 'not_null': True, 'default_md5': None}
        and after == dict(before, sql_type='jsonb'), 'original-line-varchar-storage-required-no-jsonb-conversion')
    source_columns['hr_payslip_line.name'] = before
    constraints = [row for row in plan['modified_constraints']
        if row.get('name') == 'hr_contract_resource_calendar_id_fkey']
    expected_fk = {'name': 'hr_contract_resource_calendar_id_fkey', 'table_name': 'hr_contract',
        'kind': 'f', 'columns': ['resource_calendar_id'], 'referenced_schema': 'public',
        'referenced_table': 'resource_calendar', 'referenced_columns': ['id'], 'on_delete': 'n',
        'on_update': 'a', 'match': 's', 'valid': True, 'deferrable': False, 'deferred': False,
        'definition': 'FOREIGN KEY (resource_calendar_id) REFERENCES resource_calendar(id) ON DELETE SET NULL'}
    gate.require(len(constraints) == 1 and constraints[0]['before'] == expected_fk
        and constraints[0]['after'] == dict(expected_fk, on_delete='r',
            definition='FOREIGN KEY (resource_calendar_id) REFERENCES resource_calendar(id) ON DELETE RESTRICT')
        and constraints[0]['accepted'] is False, 'original-calendar-set-null-fk-contract-required')
    return {'columns': source_columns, 'calendar_foreign_key': expected_fk,
        'remaining_schema_differences_admitted': False, 'existing_jsonb_line_conversion_admitted': False}


def _assignment(cls, field):
    rows = [node for node in cls.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == field for target in node.targets)]
    gate.require(len(rows) == 1, 'unique-storage-field-declaration-required')
    return rows[0]


def _expected_ast(tree, filename):
    tree = copy.deepcopy(tree)
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    gate.require(len(classes) == 1, 'single-real-storage-provider-class-required')
    cls = classes[0]
    if filename.endswith('hr_payslip_line.py'):
        gate.require(not any(isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
            and target.id == 'name' for target in node.targets) for node in cls.body), 'line-name-override-already-present')
        cls.body.insert(cls.body.index(_assignment(cls, '_order')) + 1,
            ast.parse('name = fields.Char(required=True, translate=False)').body[0])
    else:
        field = 'resource_calendar_id' if filename.endswith('hr_contract.py') else 'name'
        call = _assignment(cls, field).value
        expected_type = 'Many2one' if field == 'resource_calendar_id' else 'Char'
        gate.require(isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name) and call.func.value.id == 'fields'
            and call.func.attr == expected_type, 'real-storage-field-api-required')
        required = [keyword for keyword in call.keywords if keyword.arg == 'required']
        gate.require(len(required) == 1 and isinstance(required[0].value, ast.Constant)
            and required[0].value.value is True and not any(keyword.arg == 'ondelete' for keyword in call.keywords),
            'pinned-original-storage-keyword-policy-drift')
        required[0].value = ast.Constant(False)
        if field == 'resource_calendar_id':
            call.keywords.insert(call.keywords.index(required[0]) + 1,
                ast.keyword(arg='ondelete', value=ast.Constant('set null')))
    return tree


def plan_storage(files, schema_plan, *, anchor_properties=False):
    """Pure three-declaration plan for normal NUMERIC or anchored properties."""
    gate.require(type(anchor_properties) is bool, 'explicit-storage-input-profile-required')
    manifest = ast.literal_eval(files['__manifest__.py'].decode('utf-8-sig'))
    gate.require(manifest.get('license') == 'LGPL-3' and manifest['version'] == '18.0.1.4.0',
        'pinned-free-storage-provider-required')
    source = source_storage_contract(schema_plan)
    candidate = dict(files)
    for filename, digest in PINNED_SOURCE.items():
        if anchor_properties and filename.endswith('hr_payslip_line.py'):
            digest = ANCHOR_PROPERTY_LINE_SHA256
        raw = files[filename]
        gate.require(sha(raw) == digest, 'pinned-storage-provider-source-drift')
        before, after = EDITS[filename]
        gate.require(raw.count(before) == 1, 'unique-storage-byte-span-required')
        changed = raw.replace(before, after, 1)
        expected = _expected_ast(ast.parse(raw.decode('utf-8')), filename)
        gate.require(ast.dump(expected, include_attributes=False) == ast.dump(ast.parse(changed.decode('utf-8')),
            include_attributes=False), 'unrelated-storage-provider-ast-change')
        candidate[filename] = changed
    return candidate, source


def _snapshot(folder):
    gate.require(folder.is_dir() and not folder.is_symlink(), 'private-storage-provider-directory-required')
    paths = [path for path in folder.rglob('*') if '__pycache__' not in path.parts]
    gate.require(not any(path.is_symlink() for path in paths), 'storage-provider-symlinks-rejected')
    return {path.relative_to(folder).as_posix(): path.read_bytes() for path in paths if path.is_file()}


def _apply(oca, engine, schema_plan, *, capsule=None):
    oca, engine, schema_plan = map(Path, (oca, engine, schema_plan))
    raw_plan = schema_plan.read_bytes()
    gate.require(sha(raw_plan) == SCHEMA_PLAN_SHA256, 'sealed-original-storage-plan6977-required')
    plan = json.loads(raw_plan)
    original = numeric.source_files(oca)
    before = numeric.plan(original)
    if capsule is not None:
        raw_capsule = Path(capsule).read_bytes()
        gate.require(sha(raw_capsule) == company.CAPSULE_SHA256, 'sealed-original120-storage-capsule-required')
        data = json.loads(raw_capsule)
        before, _ = company.plan(before, data)
        modules, _ = properties.plan({'payroll': before,
            'payroll_account': properties.accounting_source_files(oca)}, data)
        before = modules['payroll']
    output = engine.resolve() / 'payroll'
    gate.require(engine.resolve().is_relative_to(Path('/opt/steps-validation'))
        and engine.resolve() != oca.resolve(), 'private-first-init-storage-engine-required')
    gate.require(numeric.hashes(_snapshot(output)) == numeric.hashes(before), 'storage-derivation-input-pipeline-drift')
    candidate, source_contract = plan_storage(before, plan, anchor_properties=capsule is not None)
    receipt = engine.resolve().parent / REPORT
    gate.require(not receipt.exists(), 'new-first-init-storage-receipt-required')
    for filename in EDITS:
        (output / filename).write_bytes(candidate[filename])
    gate.require(numeric.hashes(_snapshot(output)) == numeric.hashes(candidate), 'first-init-storage-output-drift')
    report = {'schema': 1, 'profile': 'original-three-storage-contracts-first-init',
        'input_profile': 'anchored-properties' if capsule is not None else 'normal-numeric',
        'oca_pin': numeric.PIN, 'license': 'LGPL-3', 'builder_sha256': sha(Path(__file__).read_bytes()),
        'schema_plan_sha256': SCHEMA_PLAN_SHA256, 'source_review_sha256': REVIEW_SHA256,
        'source_catalog_sha256': CATALOG_SHA256,
        'capsule_sha256': company.CAPSULE_SHA256 if capsule is not None else None,
        'original_source_files': numeric.hashes(original), 'input_files': numeric.hashes(before),
        'candidate_files': numeric.hashes(candidate), 'changed_files': list(EDITS),
        'field_policy': FIELD_POLICY, 'original_storage_contract': source_contract,
        'runtime_methods_changed': False, 'defaults_changed': False, 'imports_changed': False,
        'models_changed': False, 'manifest_versions_changed': False, 'database_accessed': False,
        'source_checkout_changed': False, 'existing_values_converted': False,
        'existing_jsonb_line_conversion_admitted': False, 'operational_acceptance': False,
        'integral_conversion': False, 'deadline_resolved': False}
    with os.fdopen(os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write('\n')
    return report


def apply_normal_storage_derivation(oca, engine, schema_plan):
    """Normal NUMERIC engine only: no adoption/company/property derivation."""
    return _apply(oca, engine, schema_plan)


def apply_anchor_storage_derivation(oca, engine, schema_plan, capsule):
    """After existing numeric/company/properties, before any manifest changes."""
    return _apply(oca, engine, schema_plan, capsule=capsule)
