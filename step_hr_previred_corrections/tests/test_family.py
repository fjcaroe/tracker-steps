"""Paid retroactive allowance exports once from an explicit native rule."""
from types import SimpleNamespace
from odoo.tests import tagged
from odoo.addons.step_hr_previred.tests.common import PreviredCase, make_row


@tagged('post_install', '-at_install')
class TestFamilyRetroactive(PreviredCase):
    def prepare(self, amount=594, ccaf='02', classified=True):
        employee = self.make_employee('Retroactive fixture', '18656818-4', self.dep_admin)
        slip = self.make_payslip(employee, self.dep_admin, state='draft')
        slip.worked_days_line_ids
        rule = self.env['hr.salary.rule'].create({
            'name': 'Explicit retroactive fixture', 'code': 'ARBITRARY_CODE',
            'category_id': self.env['hr.salary.rule.category'].search([], limit=1).id,
            'struct_id': self.structure.id,
            'step_previred_family_retroactive': classified,
        })
        line = self.env['hr.payslip.line'].create({
            'slip_id': slip.id, 'salary_rule_id': rule.id,
            'employee_id': employee.id, 'contract_id': slip.contract_id.id,
            'name': rule.name, 'code': rule.code,
            'category_id': rule.category_id.id, 'amount': amount,
            'quantity': 1, 'rate': 100,
        })
        self.env.flush_all()
        slip.state = 'done'
        # Represent the imported/closed monetary evidence directly. Creating a
        # line without running the full engine leaves a zero total in Enterprise.
        self.env.cr.execute('UPDATE hr_payslip_line SET total=%s WHERE id=%s',
                            (amount, line.id))
        line.invalidate_recordset(['total'])
        row = make_row(overrides={22: '22601', 23: '0', 83: ccaf})
        annex = make_row(line_type='01', overrides={23: '0'})
        record = SimpleNamespace(principal=row, rows=[row, annex],
                                 annexes=[annex], rut='18656818', dv='4',
                                 department_label='Fixture')
        dataset = SimpleNamespace(spec_version='84', issues=[], period='202608')
        return slip, line, record, dataset, annex

    def test_paid_total_goes_only_to_23(self):
        slip, line, record, dataset, annex = self.prepare()
        # Deliberately preserve an imported total that differs from its inputs.
        self.env.cr.execute('UPDATE hr_payslip_line SET total=594, amount=1000 WHERE id=%s', (line.id,))
        line.invalidate_recordset()
        self.env['step.previred.extractor']._enrich_official_fields(record, slip, dataset)
        self.assertEqual(record.principal[22], '594')
        self.assertEqual(record.principal[21], '22601')
        self.assertEqual(annex[22], '0')
        self.env.cr.execute('SELECT total FROM hr_payslip_line WHERE id=%s', (line.id,))
        self.assertEqual(self.env.cr.fetchone()[0], 594)

    def test_unclassified_rule_is_not_guessed_from_name_or_code(self):
        slip, _, record, dataset, _ = self.prepare(classified=False)
        self.env['step.previred.extractor']._enrich_official_fields(record, slip, dataset)
        self.assertEqual(record.principal[22], '0')

    def test_imported_zero_is_preserved_instead_of_recomputed(self):
        slip, line, record, dataset, _ = self.prepare(amount=1000)
        self.env.cr.execute('UPDATE hr_payslip_line SET total=0 WHERE id=%s', (line.id,))
        line.invalidate_recordset()
        self.env['step.previred.extractor']._enrich_official_fields(record, slip, dataset)
        self.assertEqual(record.principal[22], '0')

    def test_multiple_classified_lines_are_summed_and_rounded_once(self):
        slip, line, record, dataset, _ = self.prepare(amount=300.25)
        second = line.copy({'amount': 294.25, 'code': line.code,
                            'category_id': line.category_id.id})
        self.env.flush_all()
        self.env.cr.execute('UPDATE hr_payslip_line SET total=294.25 WHERE id=%s', (second.id,))
        second.invalidate_recordset(['total'])
        self.env['step.previred.extractor']._enrich_official_fields(record, slip, dataset)
        self.assertEqual(record.principal[22], '595')
        self.assertEqual(second.slip_id, slip)

    def test_no_ccaf_blocks_export(self):
        slip, _, record, dataset, _ = self.prepare(ccaf='00')
        self.env['step.previred.extractor']._enrich_official_fields(record, slip, dataset)
        self.assertTrue(any(issue.code == 'family_retroactive_without_ccaf'
                            and issue.is_error for issue in dataset.issues))

    def test_negative_retroactive_is_not_silently_made_positive(self):
        slip, _, record, dataset, _ = self.prepare(amount=-594)
        self.env['step.previred.extractor']._enrich_official_fields(record, slip, dataset)
        self.assertTrue(any(issue.code == 'family_retroactive_invalid'
                            and issue.is_error for issue in dataset.issues))
