"""CCAF amounts survive the supplier's incorrect zero-day attendance gate."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from odoo.tests import tagged
from odoo.addons.step_hr_previred.tests.common import PreviredCase, make_row


@tagged('post_install', '-at_install')
class TestCcafAttendance(PreviredCase):
    def normalize(self, overrides=None, rate=4.2):
        row = make_row(overrides={13: '30', 64: '750000', 70: '21000',
                                  75: '07', 83: '02', 84: '00000000',
                                  90: '00000000', **(overrides or {})})
        annex = make_row(line_type='01', overrides={84: '0', 90: '0'})
        record = SimpleNamespace(principal=row, rows=[row, annex],
                                 department_label='Fixture')
        dataset = SimpleNamespace(issues=[])
        slip = SimpleNamespace(date_from=date(2026, 10, 1),
                               date_to=date(2026, 10, 31))
        model = type(self.env['previred.indicator'])
        indicator = SimpleNamespace(ccaf_empleadores_afiliados=rate)
        with patch.object(model, 'search', return_value=indicator) as search:
            self.env['step.previred.extractor']._restore_ccaf_fields(
                record, slip, dataset)
        return row, annex, dataset.issues, search

    def test_missing_ccaf_uses_same_period_and_keeps_fonasa(self):
        row, annex, issues, search = self.normalize()
        self.assertEqual((row[83], row[89], row[69]),
                         ('750000', '31500', '21000'))
        self.assertEqual((annex[83], annex[89]), ('0', '0'))
        self.assertIn(('date', '>=', date(2026, 10, 1)), search.call_args.args[0])
        self.assertIn(('date', '<=', date(2026, 10, 31)), search.call_args.args[0])
        self.assertEqual(issues[0].code, 'ccaf_attendance_restored')

    def test_existing_amounts_are_preserved(self):
        row, _, issues, search = self.normalize({84: '750000', 90: '31501'})
        self.assertEqual(row[89], '31501')
        self.assertFalse(issues)
        search.assert_not_called()

    def test_isapre_no_ccaf_and_no_attendance_are_unchanged(self):
        for values in ({75: '01'}, {83: '00'}, {13: '0'}, {64: '0'}):
            row, _, issues, search = self.normalize(values)
            self.assertEqual((row[83], row[89]), ('00000000', '00000000'))
            self.assertFalse(issues)
            search.assert_not_called()

    def test_missing_indicator_blocks_instead_of_inventing_rate(self):
        row, _, issues, _ = self.normalize(rate=0)
        self.assertEqual(row[89], '00000000')
        self.assertEqual(issues[0].code, 'ccaf_rate_missing')
        self.assertTrue(issues[0].is_error)

    def test_core_restores_attendance_before_bridge_contributions(self):
        employee = self.make_employee('CCAF fixture', '18656818-4', self.dep_admin)
        slip = self.make_payslip(employee, self.dep_admin)
        slip.worked_days_line_ids.unlink()
        self.env['hr.payslip.worked_days'].create({
            'payslip_id': slip.id, 'name': 'Asistencia',
            'work_entry_type_id': self.env.ref('hr_work_entry.work_entry_type_attendance').id,
            'number_of_days': 30, 'number_of_hours': 240,
        })
        raw = make_row(rut='18656818', dv='4', overrides={
            13: '0', 64: '750000', 70: '21000', 75: '07', 83: '02',
            84: '00000000', 90: '00000000'})
        indicator = SimpleNamespace(ccaf_empleadores_afiliados=4.2)
        with patch.object(type(self.env['previred.indicator']), 'search', return_value=indicator):
            dataset = self.build([raw], spec_version='98')
        row = dataset.records[0].principal
        self.assertEqual((row[12], row[83], row[89]), ('30', '750000', '31500'))
        self.assertEqual(slip.worked_days_line_ids.number_of_days, 30)
