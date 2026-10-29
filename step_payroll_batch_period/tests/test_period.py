from unittest.mock import patch
from odoo import fields
from odoo.tests import TransactionCase, tagged
from ..models import _PERIOD_SCOPE


@tagged('post_install','-at_install')
class BatchPeriodCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.calendar = cls.env['resource.calendar'].create({'name':'QA Batch Santiago','tz':'America/Santiago'})
        cls.kind = cls.env.ref('hr_work_entry.work_entry_type_attendance')

    def contract(self, name):
        employee=self.env['hr.employee'].create({'name':name,'company_id':self.env.company.id})
        return self.env['hr.contract'].create({'name':name,'employee_id':employee.id,
            'company_id':self.env.company.id,'date_start':'2026-01-01',
            'wage':1000,'resource_calendar_id':self.calendar.id})

    def entry(self, contract, start, stop):
        return self.env['hr.work.entry'].create({'name':'QA Batch Entry',
            'employee_id':contract.employee_id.id,'contract_id':contract.id,
            'date_start':start,'date_stop':stop,'work_entry_type_id':self.kind.id})

    def test_september_conflicts_do_not_block_october_or_get_changed(self):
        contract=self.contract('QA Outside')
        rows=self.entry(contract,'2026-09-30 11:30:00','2026-09-30 16:30:00')
        rows|=self.entry(contract,'2026-09-30 11:30:00','2026-09-30 15:30:00')
        rows.write({'state':'conflict'})
        self.assertFalse(rows.with_context(_steps_batch_period=(_PERIOD_SCOPE,'2026-10-01','2026-10-31'))._check_if_error())
        self.assertEqual(set(rows.mapped('state')),{'conflict'})

    def test_real_october_conflicts_remain_blocked(self):
        contract=self.contract('QA Inside')
        rows=self.entry(contract,'2026-10-05 11:30:00','2026-10-05 16:30:00')
        rows|=self.entry(contract,'2026-10-05 11:30:00','2026-10-05 15:30:00')
        self.assertTrue(rows.with_context(_steps_batch_period=(_PERIOD_SCOPE,'2026-10-01','2026-10-31'))._check_if_error())
        self.assertEqual(set(rows.mapped('state')),{'conflict'})

    def test_local_midnight_and_intersecting_overnight_entries(self):
        contract=self.contract('QA Boundary')
        outside=self.entry(contract,'2026-10-01 01:00:00','2026-10-01 03:00:00')
        crossing=self.entry(contract,'2026-10-01 02:00:00','2026-10-01 04:00:00')
        self.assertEqual((outside|crossing)._step_entries_in_batch_period('2026-10-01','2026-10-31'),crossing)

    def test_external_context_cannot_disable_normal_validation(self):
        contract=self.contract('QA Token')
        rows=self.entry(contract,'2026-09-30 11:30:00','2026-09-30 16:30:00')
        rows|=self.entry(contract,'2026-09-30 11:30:00','2026-09-30 15:30:00')
        self.assertTrue(rows.with_context(_steps_batch_period=('fake','2026-10-01','2026-10-31'))._check_if_error())

    def test_notification_identifies_all_workers_in_local_time(self):
        first=self.contract('QA Worker A');second=self.contract('QA Worker B')
        for contract in (first,second):
            self.entry(contract,'2026-10-05 11:30:00','2026-10-05 16:30:00').write({'state':'conflict'})
        run=self.env['hr.payslip.run'].create({'name':'QA Period','date_start':'2026-10-01','date_end':'2026-10-31'})
        wizard=self.env['hr.payslip.employees'].with_context(active_id=run.id).create({})
        wizard.employee_ids=first.employee_id|second.employee_id
        from odoo.addons.hr_payroll.wizard.hr_payroll_payslips_by_employees import HrPayslipEmployees
        with patch.object(HrPayslipEmployees,'compute_sheet',return_value={'type':'ir.actions.client','tag':'display_notification','params':{}}):
            result=wizard.compute_sheet()
        for text in ('QA Worker A','QA Worker B','05/10/2026 08:30','America/Santiago'):
            self.assertIn(text,result['params']['message'])
        self.assertTrue(result['params']['sticky'])
