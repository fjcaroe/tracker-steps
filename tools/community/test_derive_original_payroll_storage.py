"""Pure declaration/provenance tests; no schema mutation or Odoo execution."""
import ast
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

import derive_original_payroll_storage as derive


def schema_plan():
    calendar = {'name': 'hr_contract_resource_calendar_id_fkey', 'table_name': 'hr_contract',
        'kind': 'f', 'columns': ['resource_calendar_id'], 'referenced_schema': 'public',
        'referenced_table': 'resource_calendar', 'referenced_columns': ['id'], 'on_delete': 'n',
        'on_update': 'a', 'match': 's', 'valid': True, 'deferrable': False, 'deferred': False,
        'definition': 'FOREIGN KEY (resource_calendar_id) REFERENCES resource_calendar(id) ON DELETE SET NULL'}
    line = {'table_name': 'hr_payslip_line', 'column_name': 'name',
        'sql_type': 'character varying', 'not_null': True, 'default_md5': None}
    plan = {'schema': 1, 'oca_payroll_pin': derive.numeric.PIN, 'review_sha256': derive.REVIEW_SHA256,
        'catalog_sha256': derive.CATALOG_SHA256, 'analysis_input': 'existing-private-S7-readonly-artifacts-only',
        'database_queries_executed': 0, 'database_writes': False, 'acceptance_authorized': False,
        'not_null_added': [], 'type_changes': [{'before': line, 'after': dict(line, sql_type='jsonb')}],
        'modified_constraints': [{'name': calendar['name'], 'before': calendar, 'accepted': False,
            'after': dict(calendar, on_delete='r', definition='FOREIGN KEY (resource_calendar_id) REFERENCES resource_calendar(id) ON DELETE RESTRICT')}]}
    for table, column, kind in [('hr_contract', 'resource_calendar_id', 'integer'),
            ('hr_payslip_worked_days', 'name', 'character varying')]:
        before = {'table_name': table, 'column_name': column, 'sql_type': kind, 'not_null': False, 'default_md5': None}
        plan['not_null_added'].append({'before': before, 'after': dict(before, not_null=True)})
    return plan


def provider(anchor=False):
    files = {'__manifest__.py': repr({'license': 'LGPL-3', 'version': '18.0.1.4.0'}).encode(),
        'models/hr_contract.py': b'''from odoo import fields, models
class HrContract(models.Model):
    _inherit = "hr.contract"
    resource_calendar_id = fields.Many2one(
        required=True, help="Employee's working schedule."
    )
    def untouched(self):
        return self.resource_calendar_id
''',
        'models/hr_payslip_worked_days.py': b'''from odoo import fields, models
class HrPayslipWorkedDays(models.Model):
    _name = "hr.payslip.worked_days"
    name = fields.Char(string="Description", required=True)
    def untouched(self):
        return self.name
''',
        'models/hr_payslip_line.py': b'''from odoo import fields, models
class HrPayslipLine(models.Model):
    _name = "hr.payslip.line"
    _inherit = "hr.salary.rule"
    _order = "contract_id, sequence"
    def untouched(self):
        return self.salary_rule_id
''',
        'models/hr_salary_rule.py': b'name = fields.Char(required=True, translate=True)\n',
        'models/hr_payslip_input.py': b'amount = fields.Float(digits=False)\n'}
    if anchor:
        files['models/hr_payslip_line.py'] = files['models/hr_payslip_line.py'].replace(
            b'    _order = "contract_id, sequence"\n', b'    _order = "contract_id, sequence"\n\n    note = fields.Text(translate=False)\n')
    return files


def derive_fixture(files, plan=None, anchor=False):
    hashes = {name: derive.sha(files[name]) for name in derive.PINNED_SOURCE}
    with patch.object(derive, 'PINNED_SOURCE', hashes), patch.object(derive, 'ANCHOR_PROPERTY_LINE_SHA256',
            derive.sha(files['models/hr_payslip_line.py'])):
        return derive.plan_storage(files, schema_plan() if plan is None else plan, anchor_properties=anchor)


class OriginalFirstInitStorageCase(unittest.TestCase):
    def test_normal_numeric_only_three_declarations_change_without_adoption_properties(self):
        files = provider(); original = dict(files)
        candidate, source = derive_fixture(files)
        self.assertEqual(files, original)
        self.assertEqual({name for name in files if candidate[name] != files[name]}, set(derive.EDITS))
        self.assertIn(b'required=False, ondelete="set null"', candidate['models/hr_contract.py'])
        self.assertIn(b'name = fields.Char(string="Description", required=False)', candidate['models/hr_payslip_worked_days.py'])
        self.assertIn(b'name = fields.Char(required=True, translate=False)', candidate['models/hr_payslip_line.py'])
        self.assertNotIn(b'note =', candidate['models/hr_payslip_line.py'])
        self.assertEqual(candidate['models/hr_salary_rule.py'], files['models/hr_salary_rule.py'])
        self.assertEqual(candidate['models/hr_payslip_input.py'], files['models/hr_payslip_input.py'])
        self.assertFalse(source['existing_jsonb_line_conversion_admitted'])

    def test_anchor_existing_scalar_note_is_preserved_and_both_modes_share_storage_policy(self):
        files = provider(True)
        candidate, source = derive_fixture(files, anchor=True)
        self.assertIn(b'note = fields.Text(translate=False)', candidate['models/hr_payslip_line.py'])
        self.assertIn(b'name = fields.Char(required=True, translate=False)', candidate['models/hr_payslip_line.py'])
        self.assertEqual(source['columns']['hr_payslip_line.name']['sql_type'], 'character varying')
        self.assertEqual(source['calendar_foreign_key']['on_delete'], 'n')

    def test_methods_imports_default_expressions_manifest_and_unrelated_files_are_exact(self):
        for anchor in (False, True):
            files = provider(anchor); candidate, _ = derive_fixture(files, anchor=anchor)
            for name, body in files.items():
                if name not in derive.EDITS:
                    self.assertEqual(body, candidate[name]); continue
                def protected(raw):
                    tree = ast.parse(raw.decode())
                    return [ast.dump(node, include_attributes=False) for node in ast.walk(tree)
                        if isinstance(node, (ast.FunctionDef, ast.Import, ast.ImportFrom))
                        or isinstance(node, ast.keyword) and node.arg == 'default']
                self.assertEqual(protected(body), protected(candidate[name]))

    def test_unpinned_nonfree_wrong_version_and_unreviewed_profile_abort(self):
        files = provider()
        with self.assertRaisesRegex(ValueError, 'pinned-storage-provider-source-drift'):
            derive.plan_storage(files, schema_plan())
        for license, version in [('OEEL-1', '18.0.1.4.0'), ('LGPL-3', '18.0.1.5.0')]:
            altered = dict(files); altered['__manifest__.py'] = repr({'license': license, 'version': version}).encode()
            with self.assertRaisesRegex(ValueError, 'pinned-free-storage-provider-required'):
                derive_fixture(altered)
        with self.assertRaises(ValueError): derive.plan_storage(files, schema_plan(), anchor_properties=1)

    def test_wrong_source_nullable_type_fk_default_or_review_seal_aborts(self):
        for change in ('calendar_required', 'days_default', 'line_jsonb', 'line_nullable', 'calendar_cascade',
                'calendar_unvalidated', 'extra_type_change', 'wrong_review', 'writes', 'accepted'):
            plan = schema_plan()
            if change == 'calendar_required': plan['not_null_added'][0]['before']['not_null'] = True
            if change == 'days_default': plan['not_null_added'][1]['before']['default_md5'] = 'not-null'
            if change == 'line_jsonb': plan['type_changes'][0]['before']['sql_type'] = 'jsonb'
            if change == 'line_nullable': plan['type_changes'][0]['before']['not_null'] = False
            if change == 'calendar_cascade': plan['modified_constraints'][0]['before']['on_delete'] = 'c'
            if change == 'calendar_unvalidated': plan['modified_constraints'][0]['before']['valid'] = False
            if change == 'extra_type_change': plan['type_changes'].append(deepcopy(plan['type_changes'][0]))
            if change == 'wrong_review': plan['review_sha256'] = '0' * 64
            if change == 'writes': plan['database_writes'] = True
            if change == 'accepted': plan['acceptance_authorized'] = True
            with self.subTest(change=change), self.assertRaises(ValueError): derive_fixture(provider(), plan)

    def test_second_application_or_changed_classical_name_declaration_cannot_be_smuggled(self):
        files = provider(); candidate, _ = derive_fixture(files)
        with self.assertRaises(ValueError): derive_fixture(candidate)
        files = provider(); files['models/hr_payslip_line.py'] += b'\n    name = fields.Char(translate=True)\n'
        with self.assertRaisesRegex(ValueError, 'line-name-override-already-present'): derive_fixture(files)

    def test_builder_storage_is_opt_in_after_properties_before_ui_with_no_database_api(self):
        source = (Path(derive.__file__).parent / 'build_original_anchor_profile.py').read_text(encoding='utf-8-sig')
        self.assertIn('original_storage=False, schema_plan=None', source)
        self.assertLess(source.index('property_derivation = apply_original_property_derivation'),
            source.index('storage_derivation = apply_anchor_storage_derivation'))
        self.assertLess(source.index('storage_derivation = apply_anchor_storage_derivation'), source.index('changes = {}'))
        tree = ast.parse(Path(derive.__file__).read_text(encoding='utf-8-sig'))
        methods = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        self.assertFalse(methods & {'connect', 'db_connect', 'execute', 'sudo', 'compute_sheet', 'commit'})
        self.assertIn('O_EXCL', Path(derive.__file__).read_text())


if __name__ == '__main__':
    unittest.main()
