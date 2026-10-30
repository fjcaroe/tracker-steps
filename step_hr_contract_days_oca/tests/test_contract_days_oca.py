"""Actual OCA/provider/T138 days, monetary storage, history and normal ACL."""
from datetime import date, datetime
from unittest import TestCase
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.addons.step_hr_contract_days.tests.common import ContractDaysFixture


@tagged('post_install', '-at_install')
class TestContractDaysOca(ContractDaysFixture, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.chile = cls._structure('Nómina Chile')

    def _values(self, slip):
        self.assertFalse(slip.env.su)
        self.assertTrue(slip.contract_id.get_work_hours(slip.date_from, slip.date_to),
            'The real private work entries must be consumable before the T138 provider is invoked.')
        values = slip._get_worked_day_lines_values()
        attendance = [row for row in values if row['work_entry_type_id'] == self.work.id]
        self.assertLessEqual(len(attendance), 1)
        return values, attendance[0] if attendance else None

    def _store(self, slip, values):
        return self.scope['hr.payslip.worked_days'].create([dict(row, payslip_id=slip.id,
            contract_id=slip.contract_id.id) for row in values])

    def test_real_unpaid_master_and_31_day_absences_keep_29_28_and_actual_form(self):
        kind = self._type('LEAVECL130')
        for count in (1, 2):
            slip = self._slip(self.chile)
            leave = self._leave(slip, kind, date(2026, 10, 1), date(2026, 10, count), unpaid=True)
            original = self._snapshot(slip)
            values, work = self._values(slip)
            self.assertEqual(work['number_of_days'], 30 - count)
            self.assertEqual(work['number_of_hours'], (30 - count) * 8)
            self.assertEqual(work['amount'], 600000 / 30 * (30 - count))
            self.assertEqual(self._snapshot(slip), original)
            rows = self._store(slip, values)
            attendance = rows.filtered(lambda row: row.work_entry_type_id == self.work)
            self.assertEqual(attendance.amount, self.company.currency_id.round(work['amount']))
            self.assertEqual(leave.holiday_status_id.work_entry_type_id, kind)
            self.assertEqual(rows.filtered(lambda row: row.work_entry_type_id == kind).amount, 0)
            before = self._snapshot(slip)
            self.assertEqual(slip._get_paid_amount(), attendance.amount)
            self.assertEqual(self._snapshot(slip), before)
        view = self.scope['hr.payslip'].get_view(view_id=self.scope.ref('payroll.hr_payslip_view_form').id, view_type='form')
        self.assertIn('worked_days_line_ids', view['arch'])
        self.assertIn('input_line_ids', view['arch'])

    def test_calendar_medical_license_keeps_supplier_divisor_31_and_stored_amount(self):
        for code in ('LIC', 'LEAVECL130'):
            slip = self._slip(self.chile)
            # A medical alias must have its own explicit global type without
            # a source unpaid master; do not reuse the real unpaid CL alias.
            kind = self._type(code, global_type=code == 'LEAVECL130')
            self._leave(slip, kind, date(2026, 10, 1), date(2026, 10, 2), unpaid=False)
            values, work = self._values(slip)
            self.assertEqual(work['number_of_days'], 29)
            self.assertAlmostEqual(work['amount'], 600000 / 31 * 29)
            rows = self._store(slip, values)
            attendance = rows.filtered(lambda row: row.work_entry_type_id == self.work)
            self.assertEqual(attendance.amount, self.company.currency_id.round(work['amount']))
            self.assertNotEqual(attendance.amount, self.company.currency_id.round(600000 / 30 * 29))

    def test_real_partial_contract_returns_nine_days_and_no_unapproved_chile_calculation(self):
        slip = self._slip(self.chile, entry=8, exit=16)
        values, work = self._values(slip)
        self.assertEqual(work['number_of_days'], 9)
        self.assertEqual(work['number_of_hours'], 72)
        self.assertAlmostEqual(work['amount'], 600000 / 31 * 9)
        rows = self._store(slip, values)
        self.assertEqual(rows.filtered(lambda row: row.work_entry_type_id == self.work).amount,
            self.company.currency_id.round(work['amount']))
        before = self._snapshot(slip)
        # Original Chile configuration remains unadopted. This bridge does not
        # disable the real financial guard merely to demonstrate a salary.
        with TestCase.assertRaises(self, UserError):
            slip.compute_sheet()
        self.assertEqual(self._snapshot(slip), before)

    def test_real_lateness_is_deducted_once_and_month_lengths_keep_approved_basis(self):
        late = self._type('LEAVECL131')
        for year, month, last in ((2026, 2, 28), (2028, 2, 29), (2026, 9, 30), (2026, 10, 31)):
            slip = self._slip(self.chile, year=year, month=month, last=last, wage=553553)
            self._entry(slip.contract_id, late, datetime(year, month, 2, 8), 2.8)
            values, work = self._values(slip)
            self.assertAlmostEqual(work['number_of_days'], 29.65)
            self.assertAlmostEqual(work['amount'], 553553 / 30 * 29.65)
            self.assertEqual(len([row for row in values if row['work_entry_type_id'] == late.id]), 1)
            rows = self._store(slip, values)
            self.assertEqual(rows.filtered(lambda row: row.work_entry_type_id == self.work).amount,
                self.company.currency_id.round(work['amount']))
            self.assertEqual(rows.filtered(lambda row: row.work_entry_type_id == late).amount, 0)
            self.assertEqual(self._values(slip)[1], work)

    def test_complete_source_acl_and_field_acl_reject_warm_sudo_without_day_writes(self):
        slip = self._slip(self.chile)
        entry = self.scope['hr.work.entry'].search([('contract_id', '=', slip.contract_id.id)], limit=1)
        self._store(slip, self._values(slip)[0])
        before = self._snapshot(slip)
        slip.sudo().read(['worked_days_line_ids'])
        rule = self.env['ir.rule'].create({'name': 'Private T138 hidden actual entry',
            'model_id': self.env['ir.model']._get_id('hr.work.entry'), 'domain_force': "[('id','!=',%s)]" % entry.id})
        # Country configuration can reject this deliberately unadopted Chile
        # profile earlier in the real MRO. Keep that gate and exercise the
        # actual source-admission method directly, without bypassing it.
        with TestCase.assertRaises(self, UserError):
            slip.sudo().compute_sheet()
        with TestCase.assertRaises(self, AccessError):
            slip.sudo()._step_contract_days_access(write=True, sources=True)
        self.assertEqual(self._snapshot(slip), before)
        rule.unlink()
        field = self.scope['hr.leave.type']._fields['unpaid']
        with patch.object(field, 'groups', 'base.group_system'):
            with TestCase.assertRaises(self, AccessError):
                slip.sudo()._get_worked_day_lines_values()
        self.assertEqual(self._snapshot(slip), before)

    def test_closed_amount_restore_uses_stored_values_after_live_policy_changes(self):
        slip = self._slip()
        slip.compute_sheet()
        slip.action_payslip_done()
        self.assertTrue(slip.move_id)
        # Change only private current policy after real validation. The frozen
        # row must not ask the live Chile provider or use the new contract wage.
        before = self._snapshot(slip)
        self.generic.name = 'Nómina Chile'
        slip.contract_id.wage = 990000
        frozen = self._snapshot(slip)
        self.assertEqual(frozen['hr_payslip'], before['hr_payslip'])
        self.assertEqual(frozen['hr_payslip_worked_days'], before['hr_payslip_worked_days'])
        days = slip.worked_days_line_ids
        days.invalidate_recordset(['amount', 'is_paid'])
        days._compute_payment()
        days.read(['amount', 'is_paid'])
        with TestCase.assertRaises(self, UserError):
            slip.sudo().compute_sheet()
        self.assertEqual(self._snapshot(slip), frozen)
