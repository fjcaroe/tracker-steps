"""Real OCA history: future contracts and recompute queues cannot rewrite the past."""
from unittest.mock import patch
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.addons.step_payroll_contracts.testing import PayrollContractMixin
from odoo.addons.step_payroll_contracts.history import assert_history_snapshots


@tagged('post_install','-at_install')
class HistoryCase(PayrollContractMixin,TransactionCase):
    payroll_group='payroll.group_payroll_manager'
    oca=True

    def worked_day(self,slip):
        kind=self.scope['hr.work.entry.type'].create({'name':'Private historical attendance','code':'PRIVATE_HISTORY'})
        day=self.scope['hr.payslip.worked_days'].create({'name':kind.name,'code':kind.code,
            'payslip_id':slip.id,'contract_id':self.contract.id,'work_entry_type_id':kind.id,
            'number_of_days':2,'number_of_hours':16})
        self.structure.use_worked_day_lines=True
        return day,kind

    def database_snapshot(self,slip):
        self.env.cr.execute('SELECT to_jsonb(t) FROM hr_payslip t WHERE id=%s',(slip.id,))
        header=self.env.cr.fetchone()
        self.env.cr.execute('SELECT to_jsonb(t) FROM hr_payslip_worked_days t WHERE payslip_id=%s ORDER BY id',(slip.id,))
        return header,self.env.cr.fetchall()

    def test_closed_days_retain_original_amount_after_future_wage_and_type_changes(self):
        slip=self.slip();day,kind=self.worked_day(slip)
        slip.compute_sheet();slip.write({'state':'done','paid':True});self.env.flush_all()
        original=self.database_snapshot(slip)
        expected=day.read(['id','amount','is_paid'])
        self.contract.wage=1200000
        kind.unpaid_structure_ids=[Command.link(self.structure.id)]
        self.env.flush_all();day.invalidate_recordset();slip.invalidate_recordset()
        self.assertEqual(day.read(['id','amount','is_paid']),expected)
        self.assertEqual(self.database_snapshot(slip),original)
        self.assertEqual(day.amount,53333)
        self.assertTrue(day.is_paid)

    def test_closed_totals_are_stored_and_do_not_evaluate_salary_lines_on_read(self):
        self.rule.code='BASIC'
        self.rule.copy({'code':'GROSS','sequence':2,'amount_python_compute':"result = result_rules['BASIC']['total']"})
        self.rule.copy({'code':'NET','sequence':3,'amount_python_compute':"result = result_rules['GROSS']['total']"})
        slip=self.slip();slip.compute_sheet();slip.state='done';self.env.flush_all()
        names=['basic_wage','gross_wage','net_wage']
        self.assertEqual([slip[name] for name in names],[800123]*3)
        original=self.database_snapshot(slip)
        with patch.object(type(slip),'_get_line_values',side_effect=AssertionError('Closed totals must not be recalculated')):
            for name in names:self.env.add_to_compute(slip._fields[name],slip)
            slip.flush_recordset(names);slip.invalidate_recordset(names)
            self.assertEqual([slip[name] for name in names],[800123]*3)
        self.assertEqual(self.database_snapshot(slip),original)

    def test_draft_days_continue_to_follow_monthly_contract_and_unpaid_type(self):
        slip=self.slip();day,kind=self.worked_day(slip)
        self.assertEqual(day.amount,53333)
        original=day.id
        self.contract.wage=900000
        self.assertEqual(day.amount,60000)
        kind.unpaid_structure_ids=[Command.link(self.structure.id)]
        self.assertFalse(day.is_paid);self.assertEqual(day.amount,0)
        self.assertEqual(day.id,original)

    def test_reopening_does_not_unlock_closed_history(self):
        slip=self.slip();slip.compute_sheet();slip.state='done'
        slip.state='cancel';slip.state='draft'
        self.assertTrue(slip.step_history_locked)
        with self.assertRaises(UserError):slip.compute_sheet()
        with self.assertRaises(UserError):slip.input_line_ids.write({'amount':999})
        with self.assertRaises(UserError):slip.write({'step_history_locked':False})
        with self.assertRaises(UserError):slip.unlink()

    def test_used_historical_rule_code_cannot_be_renamed(self):
        slip=self.slip();slip.compute_sheet();slip.state='done'
        with self.assertRaises(UserError):self.rule.code='CHANGED_HISTORY'
        self.assertEqual(self.rule.code,'LIQ')

    def test_direct_closed_creation_cannot_invent_missing_history(self):
        slip=self.slip()
        with self.assertRaises(UserError):slip.copy({'state':'done'})
        with self.assertRaises(UserError):slip.write({'date_from':slip.date_from,'state':'done'})
        self.assertFalse(slip.step_history_locked)

    def test_upgrade_is_rejected_before_creating_a_missing_snapshot_column(self):
        slip=self.slip();slip.compute_sheet();slip.state='done';self.env.flush_all()
        original=self.database_snapshot(slip)
        with self.assertRaises(UserError),self.env.cr.savepoint():
            self.env.cr.execute('ALTER TABLE hr_payslip RENAME COLUMN net_wage TO private_missing_snapshot_probe')
            assert_history_snapshots(self.env.cr)
        self.assertEqual(self.database_snapshot(slip),original)
