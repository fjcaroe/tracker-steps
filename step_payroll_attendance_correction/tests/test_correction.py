from datetime import datetime
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError
from .common import ContractDaysFixture


@tagged('post_install', '-at_install')
class CorrectionCase(ContractDaysFixture, TransactionCase):
    def case(self):
        slip = self._slip()
        entry = self._entry(slip.contract_id, self.work, datetime(2026, 10, 30, 8), 8)
        entry.write({'state': 'validated'})
        return slip, entry

    def test_manual_delete_then_change_contract_end(self):
        slip, entry = self.case()
        entry.unlink()
        self.assertFalse(entry.exists())
        slip.contract_id.date_end = '2026-10-29'
        self.assertEqual(str(slip.contract_id.date_end), '2026-10-29')
        self.assertEqual(slip.state, 'draft')

    def test_confirmed_payroll_is_protected(self):
        slip, entry = self.case()
        self.env.cr.execute("UPDATE hr_payslip SET state='done' WHERE id=%s", [slip.id])
        slip.invalidate_recordset()
        with self.cr.savepoint(), self.assertRaises(UserError):
            entry.unlink()
        self.assertTrue(entry.exists())

    def test_overlapping_confirmed_payroll_blocks_draft_exception(self):
        slip, entry = self.case()
        other = slip.copy({'number': 'PRIVATE/T143/LOCKED'})
        self.env.cr.execute("UPDATE hr_payslip SET state='done' WHERE id=%s", [other.id])
        other.invalidate_recordset()
        with self.cr.savepoint(), self.assertRaises(UserError):
            entry.unlink()

    def test_without_payroll_keeps_original_protection(self):
        slip, entry = self.case()
        slip.unlink()
        with self.cr.savepoint(), self.assertRaises(UserError):
            entry.unlink()

    def test_leave_entry_stays_protected(self):
        slip, entry = self.case()
        entry.work_entry_type_id = self._type('PRIVATE_T143_LEAVE')
        entry.state = 'validated'
        with self.cr.savepoint(), self.assertRaises(UserError):
            entry.unlink()
