"""Open-ended hires and conversions retain all other declaration checks."""
from types import SimpleNamespace
from odoo.tests import TransactionCase, tagged
from odoo.addons.step_hr_previred.tests.common import make_row
from odoo.addons.step_hr_previred.tools import previred


@tagged('post_install', '-at_install')
class TestOpenEndedMovementDates(TransactionCase):
    def validate(self, movements):
        rows = [make_row(line_type='01', overrides={15: code, 16: start, 17: end})
                for code, start, end in movements]
        record = SimpleNamespace(rut='12345678', dv='9', annexes=rows,
                                 department_label='Fixture')
        original = [list(row) for row in rows]
        issues = []
        for row in rows:
            issues.extend(previred.validate_annex_conditions(
                row, 'RUT 12345678-9', 'Fixture'))
        dataset = SimpleNamespace(records=[record], issues=issues)
        result = self.env['step.previred.extractor']._allow_open_ended_movements(dataset)
        self.assertEqual(rows, original, 'Never fabricate or modify a movement date')
        return result

    def test_hire_and_conversion_have_no_required_end_date(self):
        for code in ('1', '01', '8', '08'):
            result = self.validate([(code, '01-10-2026', '')])
            self.assertFalse(result.issues)

    def test_start_date_remains_required(self):
        for code in ('1', '8'):
            result = self.validate([(code, '', '')])
            self.assertEqual([issue.code for issue in result.issues],
                             ['movement_date_from_required'])

    def test_mixed_medical_leave_still_requires_its_end(self):
        result = self.validate([('1', '01-10-2026', ''), ('3', '02-10-2026', ''),
                                ('8', '01-10-2026', '')])
        self.assertEqual([issue.code for issue in result.issues],
                         ['movement_date_to_required'])
        self.assertIn('personal 3', result.issues[0].message)

    def test_existing_dates_are_not_rewritten(self):
        result = self.validate([('8', '01-10-2026', '31-10-2026')])
        self.assertFalse(result.issues)
