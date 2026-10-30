import hashlib
import json
import unittest
from unittest.mock import patch

import derive_original_anchor_company as derive
from test_plan_original_payroll_bootstrap import fixture


class OriginalCompanyDerivationCase(unittest.TestCase):
    def inputs(self):
        files = {
            '__manifest__.py': repr({'license': 'LGPL-3', 'version': '18.0.1.4.0'}).encode(),
            derive.FILE: b'''from odoo import fields, models
class HrPayrollStructure(models.Model):
    _name = "hr.payroll.structure"
    name = fields.Char(required=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    parent_id = fields.Many2one("hr.payroll.structure", default=_get_parent)
    require_code = fields.Boolean(compute="_compute_require_code", default=lambda self: self._compute_require_code())
''',
            'models/hr_salary_rule.py': b'''from odoo import fields, models
class HrSalaryRule(models.Model):
    _name = "hr.salary.rule"
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    sequence = fields.Integer(required=True, default=5)
''',
            'models/hr_salary_rule_category.py': b'''from odoo import fields, models
class HrSalaryRuleCategory(models.Model):
    _name = "hr.salary.rule.category"
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
''',
            'models/hr_payslip_input.py': b'amount = fields.Float(digits=False)\n',
        }
        capsule, _, _ = fixture()
        for table, data in capsule['tables'].items():
            rows = [dict(json.loads(raw), name='Synthetic master', sequence=5) for raw in data['rows_json']]
            data['rows_json'] = [json.dumps(row) for row in rows]
            data['rows_sha256'] = hashlib.sha256('\n'.join(data['rows_json']).encode()).hexdigest()
            data['columns'] = [{'name': 'id', 'pg_type': 'integer', 'not_null': True},
                               {'name': 'name', 'pg_type': 'character varying', 'not_null': True},
                               {'name': 'sequence', 'pg_type': 'integer', 'not_null': True}]
        return files, capsule

    def plan(self, files, capsule):
        with patch.object(derive, 'FILE_SHA256', hashlib.sha256(files[derive.FILE]).hexdigest()):
            return derive.plan(files, capsule)

    def test_only_required_true_span_changes_and_defaults_and_numeric_input_stay_exact(self):
        files, capsule = self.inputs()
        result, audit = self.plan(files, capsule)
        self.assertEqual([name for name in files if files[name] != result[name]], [derive.FILE])
        self.assertEqual(result[derive.FILE], files[derive.FILE].replace(b'required=True, default=lambda', b'required=False, default=lambda'))
        self.assertEqual(result['models/hr_payslip_input.py'], files['models/hr_payslip_input.py'])
        self.assertEqual(audit['original_master_count'], 120)
        self.assertFalse(audit['default_backfill_admitted'])

    def test_exact_four_nullable_precolumns_include_parent_default_and_no_new_owner(self):
        files, capsule = self.inputs()
        _, audit = self.plan(files, capsule)
        columns = audit['required_precreated_columns']
        self.assertEqual({(row['table'], row['column']) for row in columns}, derive.EXPECTED_NEW_DEFAULTS)
        self.assertTrue(all(row['nullable'] is True and row['sql_default'] is None for row in columns))
        self.assertTrue(all(row['required_before_orm'] is False for row in columns))
        self.assertEqual(next(row for row in columns if row['column'] == 'parent_id')['existing_rows_must_remain_sql_null'], 4)
        self.assertEqual(audit['nonstored_default_fields'], [{'model': 'hr.payroll.structure',
            'field': 'require_code', 'stored': False, 'file': derive.FILE}])

    def test_new_unreviewed_defaulted_master_column_aborts(self):
        files, capsule = self.inputs()
        files['models/hr_salary_rule.py'] += b'    inferred_owner = fields.Integer(default=1)\n'
        with self.assertRaisesRegex(ValueError, 'unreviewed-new-defaulted-original-master-column'):
            self.plan(files, capsule)

    def test_required_default_over_existing_null_aborts_without_rewriting_source(self):
        files, capsule = self.inputs()
        files['models/hr_salary_rule.py'] += b'    source_value = fields.Char(required=True, default="inferred")\n'
        capsule['tables']['hr_salary_rule']['columns'].append(
            {'name': 'source_value', 'pg_type': 'character varying', 'not_null': False})
        before = dict(files)
        with self.assertRaisesRegex(ValueError, 'required-field-would-rewrite-original-null-values'):
            self.plan(files, capsule)
        self.assertEqual(files, before)

    def test_precreated_column_is_insufficient_if_another_default_is_required(self):
        files, capsule = self.inputs()
        files['models/hr_salary_rule_category.py'] = files['models/hr_salary_rule_category.py'].replace(
            b'default=lambda', b'required=True, default=lambda')
        with self.assertRaisesRegex(ValueError, 'precreated-defaulted-master-column-must-be-optional'):
            self.plan(files, capsule)

    def test_source_hash_version_license_and_default_expression_cannot_drift(self):
        files, capsule = self.inputs()
        with self.assertRaisesRegex(ValueError, 'pinned-structure-source-drift'):
            derive.plan(files, capsule)
        for field, value in [('license', 'OEEL-1'), ('version', '18.0.9.0.0')]:
            changed = dict(files)
            manifest = {'license': 'LGPL-3', 'version': '18.0.1.4.0', field: value}
            changed['__manifest__.py'] = repr(manifest).encode()
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'pinned-free-payroll-manifest-required'):
                self.plan(changed, capsule)
        files[derive.FILE] = files[derive.FILE].replace(b'lambda self: self.env.company', b'lambda self: self.env.other_company')
        with self.assertRaisesRegex(ValueError, 'original-company-required-or-new-record-default-drift'):
            self.plan(files, capsule)


if __name__ == '__main__':
    unittest.main()
