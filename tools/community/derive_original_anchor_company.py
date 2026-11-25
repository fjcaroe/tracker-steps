"""Pinned LGPL pre-first-init derivation for global original payroll masters.

Only structure.company_id.required changes True -> False. Defaults and engine
methods stay intact for genuinely new ORM records. The coordinator must ALSO
precreate the four reported nullable columns without defaults before any Odoo
initialization: an optional new field can otherwise backfill existing rows.
No database access or original master write is performed by this builder.
"""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path

import build_numeric_input_engine as numeric
import payroll_configuration_adoption_preflight as gate


FILE = 'models/hr_payroll_structure.py'
FILE_SHA256 = '380d8a8d82367ed7abdc751a20deab019e440dc05f04e61b05efd7b62cac27b0'
REPORT = 'oca-original-global-company-derivation.json'
CAPSULE_SHA256 = '14b18ced97032ec27c306ed4c71c46f0c3d56e324d0eace4f0c8f2c86544e140'
EXPECTED_NEW_DEFAULTS = {
    ('hr_payroll_structure', 'company_id'), ('hr_payroll_structure', 'parent_id'),
    ('hr_salary_rule', 'company_id'), ('hr_salary_rule_category', 'company_id'),
}
MODEL_TABLES = {value: name for name, value in gate.TABLES.items()}


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _model(cls):
    for attribute in ('_name', '_inherit'):
        for node in cls.body:
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
                    and target.id == attribute for target in node.targets):
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    return node.value.value
    return None


def _fields(files):
    for filename, raw in sorted(files.items()):
        if not filename.startswith('models/') or not filename.endswith('.py'):
            continue
        for cls in ast.parse(raw.decode('utf-8-sig')).body:
            if not isinstance(cls, ast.ClassDef) or _model(cls) not in MODEL_TABLES:
                continue
            for node in cls.body:
                if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                        and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Call)):
                    continue
                call = node.value
                if not (isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name)
                        and call.func.value.id == 'fields'):
                    continue
                yield filename, cls, node, call


def initializer_audit(files, capsule):
    """Classify actual OCA field initializers, without exposing master values."""
    rows = gate.capsule_rows(capsule)
    found, nonstored, precreate = [], [], []
    for filename, cls, assignment, call in _fields(files):
        model, name = _model(cls), assignment.targets[0].id
        table = MODEL_TABLES[model]
        keywords = {item.arg: item.value for item in call.keywords}
        field_type = call.func.attr
        computed = 'compute' in keywords
        store = ast.literal_eval(keywords['store']) if 'store' in keywords else not computed and 'related' not in keywords
        required = ast.literal_eval(keywords['required']) if 'required' in keywords else False
        gate.require(type(store) is bool and type(required) is bool, 'nonliteral-master-field-storage-policy')
        if field_type in ('One2many', 'Many2many') or not store:
            if 'default' in keywords:
                nonstored.append({'model': model, 'field': name, 'stored': False, 'file': filename})
            continue
        original = {column['name']: column for column in capsule['tables'][table]['columns']}
        exists = name in original
        nulls = sum(row.get(name) is None for row in rows[table]) if exists else len(rows[table])
        default = keywords.get('default')
        item = {'model': model, 'table': table, 'field': name, 'field_type': field_type,
            'file': filename, 'required': required, 'has_explicit_default': default is not None,
            'original_column_exists': exists, 'original_null_rows': nulls,
            'original_not_null': original[name]['not_null'] if exists else None}
        if default is not None:
            # Hash the free source expression, never source customer values.
            item['default_ast_sha256'] = _digest(ast.dump(default).encode())
        found.append(item)
        if not exists and default is not None:
            gate.require((table, name) in EXPECTED_NEW_DEFAULTS and field_type == 'Many2one',
                         'unreviewed-new-defaulted-original-master-column')
            gate.require(not required, 'precreated-defaulted-master-column-must-be-optional')
            precreate.append({'table': table, 'column': name, 'sql_type': 'integer',
                'nullable': True, 'sql_default': None, 'required_before_orm': False,
                'existing_rows_must_remain_sql_null': len(rows[table]),
                'default_remains_for_new_orm_records': True})
        if exists and required and not original[name]['not_null'] and nulls:
            gate.require(default is None, 'required-field-would-rewrite-original-null-values')
    gate.require({(row['table'], row['column']) for row in precreate} == EXPECTED_NEW_DEFAULTS,
                 'expected-four-original-master-initializers-drift')
    return {'stored_fields': found, 'nonstored_default_fields': nonstored,
        'required_precreated_columns': sorted(precreate, key=lambda row: (row['table'], row['column'])),
        'original_master_count': sum(len(value) for value in rows.values()),
        'default_backfill_admitted': False, 'database_accessed': False}


def plan(files, capsule):
    manifest = ast.literal_eval(files['__manifest__.py'].decode('utf-8-sig'))
    gate.require(manifest.get('license') == 'LGPL-3' and manifest['version'] == '18.0.1.4.0',
                 'pinned-free-payroll-manifest-required')
    raw = files[FILE]
    gate.require(_digest(raw) == FILE_SHA256, 'pinned-structure-source-drift')
    tree = ast.parse(raw.decode())
    declarations = [(cls, assignment, call) for filename, cls, assignment, call in _fields({FILE: raw})
                    if _model(cls) == 'hr.payroll.structure' and assignment.targets[0].id == 'company_id']
    gate.require(len(declarations) == 1, 'unique-real-structure-company-declaration-required')
    call = declarations[0][2]
    gate.require(call.func.attr == 'Many2one' and call.args
        and isinstance(call.args[0], ast.Constant) and call.args[0].value == 'res.company',
        'real-company-many2one-required')
    required = [keyword for keyword in call.keywords if keyword.arg == 'required']
    defaults = [keyword for keyword in call.keywords if keyword.arg == 'default']
    gate.require(len(required) == len(defaults) == 1
        and isinstance(required[0].value, ast.Constant) and required[0].value.value is True
        and ast.dump(defaults[0].value) == ast.dump(ast.parse('lambda self: self.env.company', mode='eval').body),
        'original-company-required-or-new-record-default-drift')
    node = required[0].value
    lines = raw.splitlines(keepends=True)
    start = sum(map(len, lines[:node.lineno - 1])) + node.col_offset
    end = sum(map(len, lines[:node.end_lineno - 1])) + node.end_col_offset
    gate.require(raw[start:end] == b'True', 'reviewed-required-byte-span-missing')
    changed = raw[:start] + b'False' + raw[end:]
    expected = copy.deepcopy(tree)
    expected_company = next(node for node in ast.walk(expected) if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'company_id' for target in node.targets))
    next(keyword for keyword in expected_company.value.keywords if keyword.arg == 'required').value = ast.Constant(False)
    gate.require(ast.dump(expected, include_attributes=False) == ast.dump(ast.parse(changed.decode()), include_attributes=False),
                 'unrelated-engine-ast-change')
    candidate = dict(files)
    candidate[FILE] = changed
    audit = initializer_audit(candidate, capsule)
    gate.require(audit['original_master_count'] == 120, 'original-120-master-contract-required')
    return candidate, audit


def apply_original_company_derivation(oca, engine, capsule, expected_capsule_sha256=CAPSULE_SHA256):
    """Call after numeric.build(), BEFORE the anchor's UI manifest derivation.

    The destination must already be exactly the reviewed NUMERIC derivation.
    This helper changes only one field keyword and writes a private receipt;
    the coordinator owns precreating all four columns and proving NULL later.
    """
    oca, engine, capsule = map(Path, (oca, engine, capsule))
    gate.require(expected_capsule_sha256 == CAPSULE_SHA256
        and _digest(capsule.read_bytes()) == expected_capsule_sha256, 'sealed-original-capsule-required')
    original = numeric.source_files(oca)
    before = numeric.plan(original)
    output = engine.resolve() / 'payroll'
    gate.require(engine.resolve().is_relative_to(Path('/opt/steps-validation'))
        and output.is_dir() and not output.is_symlink() and output.resolve() != (oca / 'payroll').resolve(),
        'existing-private-derived-engine-required')
    actual = {p.relative_to(output).as_posix(): p.read_bytes() for p in output.rglob('*')
              if p.is_file() and '__pycache__' not in p.parts}
    gate.require(numeric.hashes(actual) == numeric.hashes(before), 'numeric-first-engine-input-drift')
    candidate, audit = plan(before, json.loads(capsule.read_text()))
    receipt_path = engine.resolve().parent / REPORT
    gate.require(not receipt_path.exists(), 'new-company-derivation-receipt-required')
    report = {'schema': 1, 'profile_version': 1, 'profile': 'original-global-company-first-init',
        'oca_pin': numeric.PIN, 'license': 'LGPL-3', 'manifest_version_before': '18.0.1.4.0',
        'manifest_version_after': '18.0.1.4.0', 'manifest_changed_by_this_derivation': False,
        'source_files': numeric.hashes(original), 'numeric_input_files': numeric.hashes(before),
        'candidate_files': numeric.hashes(candidate), 'changed_files_from_numeric': [FILE],
        'supported_field_keyword': {'model': 'hr.payroll.structure', 'field': 'company_id', 'required': False},
        'new_record_defaults_changed': False, 'runtime_methods_changed': False,
        'initializer_audit': audit, 'capsule_sha256': expected_capsule_sha256,
        'builder_sha256': _digest(Path(__file__).read_bytes()), 'database_accessed': False,
        'source_checkout_changed': False, 'existing_rows_rewritten': False,
        'columns_precreated_by_builder': False, 'operational_acceptance': False}
    (output / FILE).write_bytes(candidate[FILE])
    verified = {p.relative_to(output).as_posix(): p.read_bytes() for p in output.rglob('*')
                if p.is_file() and '__pycache__' not in p.parts}
    gate.require(numeric.hashes(verified) == report['candidate_files'], 'derived-engine-byte-preservation-failed')
    with os.fdopen(os.open(receipt_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write('\n')
    return report
