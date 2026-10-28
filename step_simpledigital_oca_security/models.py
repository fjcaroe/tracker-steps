"""Require country-specific data at payroll processing, never invent old master data."""
from odoo import models, _
from odoo.exceptions import UserError


class Payslip(models.Model):
    _inherit = 'hr.payslip'

    def compute_sheet(self):
        if any(slip.state not in ('draft','verify') or ('paid' in slip._fields and slip.paid) for slip in self):
            raise UserError(_('Validated or paid payroll cannot be recalculated.'))
        for slip in self:
            if slip.struct_id.name != 'Nómina Chile':
                continue
            contract=slip.contract_id
            missing=[field for field in ('contract_type_id','analytic_account_id','health_institution','pension_option') if not contract[field]]
            for field in ('hr_commune','identification_id','country_id','birthday','gender'):
                if not slip.employee_id[field]:missing.append(field)
            if missing:
                raise UserError(_('Complete Chile payroll data before calculation: %s',', '.join(missing)))
            if not {'BASIC','GROSS','NET'} <= set(slip.struct_id.rule_ids.mapped('code')):
                raise UserError(_('Adopt the original base, gross and net rules before processing Chile payroll.'))
            if not contract.get_work_hours(slip.date_from,slip.date_to):
                raise UserError(_('Generate actual work entries before calculating Chile payroll.'))
            if contract.wage_type!='monthly' or contract.schedule_pay!='monthly':
                raise UserError(_('This provider rehearsal supports audited monthly wage payroll only.'))
        with self.env.cr.savepoint():
            return super().compute_sheet()
