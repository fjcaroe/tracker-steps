"""Require country-specific data at payroll processing, never invent old master data."""
from odoo import models, _
from odoo.exceptions import UserError


class Payslip(models.Model):
    _inherit = 'hr.payslip'

    def compute_sheet(self):
        for slip in self:
            if slip.struct_id.name != 'Nómina Chile':
                continue
            contract=slip.contract_id
            missing=[field for field in ('contract_type_id','analytic_account_id','health_institution','pension_option') if not contract[field]]
            if not slip.employee_id.hr_commune:
                missing.append('hr_commune')
            if missing:
                raise UserError(_('Complete Chile payroll data before calculation: %s',', '.join(missing)))
            if contract.wage_type!='monthly' or contract.schedule_pay!='monthly':
                raise UserError(_('This provider rehearsal supports audited monthly wage payroll only.'))
        with self.env.cr.savepoint():
            return super().compute_sheet()
