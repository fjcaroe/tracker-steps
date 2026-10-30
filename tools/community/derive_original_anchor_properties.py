"""Keep original JSONB properties from the first real OCA initialization.

Four explicit field declarations, one fields import; no methods/defaults/data
change. Scalar line overrides prevent classical salary-rule inheritance from
turning newly introduced line columns into JSONB. This is a private pinned
LGPL source derivation, never a database conversion or framework patch.
"""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess

import build_numeric_input_engine as numeric
import derive_original_anchor_company as company
import payroll_configuration_adoption_preflight as gate


REPORT = 'oca-original-properties-first-init-derivation.json'
PINNED_SOURCE = {
    ('payroll', 'models/hr_salary_rule.py'): 'ad02284d3a8b3a0b6214501d461796e55d6748fa7f6025206d6d39b074fceb45',
    ('payroll', 'models/hr_payslip_line.py'): '68f23f57b04976099d8f8e0322861e6cd63ebc139eb618d19fcab3ef3916f2c3',
    ('payroll_account', 'models/hr_salary_rule.py'): 'a4b8712ffd5e4980eb121d3d021fc0952fdee95efb9fc8d9ae47958e34dc6b69',
    ('payroll_account', 'models/hr_payslip_line.py'): '5d69a8d5ce111f3f48f36c78c2e2b7669bd4722538b12e70639f4ab516a8ba96',
}
EDITS = {
    ('payroll', 'models/hr_salary_rule.py'): [
        (b'    note = fields.Text(string="Description")', b'    note = fields.Html(string="Description", translate=True)')],
    ('payroll', 'models/hr_payslip_line.py'): [
        (b'    _order = "contract_id, sequence"\n', b'    _order = "contract_id, sequence"\n\n    note = fields.Text(translate=False)\n')],
    ('payroll_account', 'models/hr_salary_rule.py'): [
        (b'    analytic_account_id = fields.Many2one("account.analytic.account")',
         b'    analytic_account_id = fields.Many2one("account.analytic.account", company_dependent=True)')],
    ('payroll_account', 'models/hr_payslip_line.py'): [
        (b'from odoo import models\n', b'from odoo import fields, models\n'),
        (b'    _inherit = "hr.payslip.line"\n',
         b'    _inherit = "hr.payslip.line"\n\n    analytic_account_id = fields.Many2one("account.analytic.account", company_dependent=False)\n')],
}


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _field(cls, name):
    rows = [node for node in cls.body if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)]
    gate.require(len(rows) == 1, 'unique-original-property-field-declaration-required')
    return rows[0]


def _expected_ast(tree, module, filename):
    tree = copy.deepcopy(tree)
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    gate.require(len(classes) == 1, 'single-real-property-provider-class-required')
    cls = classes[0]
    if filename.endswith('hr_salary_rule.py'):
        name = 'note' if module == 'payroll' else 'analytic_account_id'
        call = _field(cls, name).value
        gate.require(isinstance(call, ast.Call), 'real-original-property-call-required')
        if name == 'note':
            gate.require(call.func.attr == 'Text', 'original-rule-note-declaration-drift')
            call.func.attr = 'Html'
            call.keywords.append(ast.keyword(arg='translate', value=ast.Constant(True)))
        else:
            gate.require(call.func.attr == 'Many2one', 'original-rule-analytic-declaration-drift')
            call.keywords.append(ast.keyword(arg='company_dependent', value=ast.Constant(True)))
    elif module == 'payroll':
        node = ast.parse('note = fields.Text(translate=False)').body[0]
        cls.body.insert(cls.body.index(_field(cls, '_order')) + 1, node)
    else:
        imports = [node for node in tree.body if isinstance(node, ast.ImportFrom) and node.module == 'odoo']
        gate.require(len(imports) == 1 and [alias.name for alias in imports[0].names] == ['models'],
                     'original-line-import-contract-drift')
        imports[0].names.insert(0, ast.alias(name='fields'))
        node = ast.parse('analytic_account_id = fields.Many2one("account.analytic.account", company_dependent=False)').body[0]
        cls.body.insert(cls.body.index(_field(cls, '_inherit')) + 1, node)
    return tree


def source_storage_contract(capsule):
    rows = gate.capsule_rows(capsule)
    required = [('hr_salary_rule', name) for name in ('account_debit', 'account_credit', 'analytic_account_id', 'note')]
    required.append(('hr_payroll_structure', 'journal_id'))
    result = []
    for table, name in required:
        columns = [column for column in capsule['tables'][table]['columns'] if column['name'] == name]
        gate.require(len(columns) == 1 and columns[0]['pg_type'] == 'jsonb'
            and columns[0]['not_null'] is False, 'original-property-jsonb-storage-required')
        result.append({'table': table, 'column': name, 'sql_type': 'jsonb',
            'nullable': True, 'source_null_rows': sum(row[name] is None for row in rows[table]),
            'existing_values_converted': False})
    return result


def plan(modules, capsule):
    for name, version in [('payroll', '18.0.1.4.0'), ('payroll_account', '18.0.1.0.6')]:
        manifest = ast.literal_eval(modules[name]['__manifest__.py'].decode('utf-8-sig'))
        gate.require(manifest.get('license') == 'LGPL-3' and manifest['version'] == version,
                     'pinned-free-property-provider-version-required')
    candidate = {name: dict(files) for name, files in modules.items()}
    for (module, filename), source_sha in PINNED_SOURCE.items():
        raw = modules[module][filename]
        gate.require(_sha(raw) == source_sha, 'pinned-property-source-drift')
        changed = raw
        for before, after in EDITS[module, filename]:
            gate.require(changed.count(before) == 1, 'unique-pinned-property-byte-span-required')
            changed = changed.replace(before, after, 1)
        expected = _expected_ast(ast.parse(raw.decode('utf-8')), module, filename)
        gate.require(ast.dump(expected, include_attributes=False) == ast.dump(ast.parse(changed.decode('utf-8')), include_attributes=False),
                     'unrelated-original-property-engine-code-change')
        candidate[module][filename] = changed
    return candidate, source_storage_contract(capsule)


def accounting_source_files(oca):
    oca = Path(oca).resolve()
    command = ['git', '--no-optional-locks', '--git-dir=' + str(oca / '.git'), '--work-tree=' + str(oca)]
    gate.require(subprocess.check_output(command + ['rev-parse', 'HEAD'], text=True).strip() == numeric.PIN,
                 'accounting-provider-pin-drift')
    manifest = subprocess.check_output(command + ['show', numeric.PIN + ':payroll_account/__manifest__.py'])
    gate.require(ast.literal_eval(manifest.decode()).get('license') == 'LGPL-3', 'nonfree-accounting-provider-rejected')
    names = subprocess.check_output(command + ['ls-files', '-z', '--', 'payroll_account']).decode().split('\0')
    result = {}
    for name in filter(None, names):
        path = oca / name
        gate.require(path.is_file() and not path.is_symlink(), 'pinned-accounting-provider-file-required')
        raw = path.read_bytes()
        gate.require(raw == subprocess.check_output(command + ['show', numeric.PIN + ':' + name]), 'accounting-provider-file-drift')
        result[Path(name).relative_to('payroll_account').as_posix()] = raw
    return result


def apply_original_property_derivation(oca, engine, capsule, expected_capsule_sha256=company.CAPSULE_SHA256):
    """After company derivation/accounting copy; before UI manifest mutation."""
    oca, engine, capsule = map(Path, (oca, engine, capsule))
    gate.require(expected_capsule_sha256 == company.CAPSULE_SHA256
        and _sha(capsule.read_bytes()) == expected_capsule_sha256, 'sealed-original-properties-capsule-required')
    data = json.loads(capsule.read_text())
    original = numeric.source_files(oca)
    payroll, _ = company.plan(numeric.plan(original), data)
    before = {'payroll': payroll, 'payroll_account': accounting_source_files(oca)}
    gate.require(engine.resolve().is_relative_to(Path('/opt/steps-validation'))
        and engine.resolve() != oca.resolve(), 'private-original-property-engine-required')
    for module, expected in before.items():
        folder = engine.resolve() / module
        gate.require(folder.is_dir() and not folder.is_symlink(), 'private-property-provider-directory-required')
        files = {path.relative_to(folder).as_posix(): path.read_bytes() for path in folder.rglob('*')
                 if path.is_file() and '__pycache__' not in path.parts}
        gate.require(numeric.hashes(files) == numeric.hashes(expected), 'original-property-derivation-input-drift')
    candidate, source = plan(before, data)
    receipt = engine.resolve().parent / REPORT
    gate.require(not receipt.exists(), 'new-original-property-receipt-required')
    for module, filename in EDITS:
        (engine.resolve() / module / filename).write_bytes(candidate[module][filename])
    report = {'schema': 1, 'profile_version': 1, 'oca_pin': numeric.PIN, 'license': 'LGPL-3',
        'builder_sha256': _sha(Path(__file__).read_bytes()), 'capsule_sha256': expected_capsule_sha256,
        'input_files': {name: numeric.hashes(files) for name, files in before.items()},
        'candidate_files': {name: numeric.hashes(files) for name, files in candidate.items()},
        'changed_files': [module + '/' + filename for module, filename in EDITS],
        'field_policy': {'hr.salary.rule.note': {'type': 'html', 'translate': True},
            'hr.payslip.line.note': {'type': 'text', 'translate': False},
            'hr.salary.rule.analytic_account_id': {'company_dependent': True},
            'hr.payslip.line.analytic_account_id': {'company_dependent': False}},
        'original_property_storage': source, 'scalar_line_columns_are_not_claimed_preexisting': True,
        'methods_changed': False, 'defaults_changed': False, 'database_accessed': False,
        'source_checkout_changed': False, 'manifest_versions_changed': False,
        'original_values_converted': False, 'operational_acceptance': False}
    for module, expected in candidate.items():
        folder = engine.resolve() / module
        actual = {path.relative_to(folder).as_posix(): path.read_bytes() for path in folder.rglob('*')
                  if path.is_file() and '__pycache__' not in path.parts}
        gate.require(numeric.hashes(actual) == numeric.hashes(expected), 'derived-property-bytes-drift')
    with os.fdopen(os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write('\n')
    return report
