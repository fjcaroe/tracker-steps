"""Require country-specific data at payroll processing, never invent old master data."""
from odoo import api, models, _
from odoo.addons.step_payroll_contracts.history import assert_mutable, history_protected
from odoo.addons.step_payroll_contracts.configuration import configuration_report, validate_configuration
from odoo.exceptions import UserError


class Payslip(models.Model):
    _inherit = 'hr.payslip'

    def write(self,values):
        financial={'employee_id','company_id','contract_id','struct_id','date_from','date_to',
                   'line_ids','input_line_ids','worked_days_line_ids','credit_note','basic_wage','gross_wage','net_wage'}
        if financial & values.keys():assert_mutable(self)
        if 'paid' in values and any(history_protected(slip) and 'paid' in slip._fields and slip.paid!=values['paid'] for slip in self):
            raise UserError(_('Closed payroll payment status cannot be reset.'))
        return super().write(values)

    def unlink(self):
        assert_mutable(self)
        return super().unlink()

    def compute_sheet(self):
        if any(slip.state not in ('draft','verify') or ('paid' in slip._fields and slip.paid) for slip in self):
            raise UserError(_('Validated or paid payroll cannot be recalculated.'))
        for slip in self:
            if slip.struct_id.name != 'Nómina Chile':
                continue
            validate_configuration(slip.struct_id)
            contract=slip.contract_id
            missing=[field for field in ('contract_type_id','analytic_account_id','health_institution','pension_option','income_tax_type','work_schedule_id') if not contract[field]]
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


def ensure_target_open(records,values,parent):
    assert_mutable(records.mapped(parent))
    if values.get(parent):assert_mutable(records.env['hr.payslip'].browse(values[parent]))


class WorkedDays(models.Model):
    _inherit='hr.payslip.worked_days'

    @api.model_create_multi
    def create(self,values_list):
        for values in values_list:ensure_target_open(self,values,'payslip_id')
        return super().create(values_list)

    def write(self,values):
        ensure_target_open(self,values,'payslip_id')
        return super().write(values)

    def unlink(self):
        assert_mutable(self.mapped('payslip_id'))
        return super().unlink()


class Input(models.Model):
    _inherit='hr.payslip.input'

    @api.model_create_multi
    def create(self,values_list):
        for values in values_list:ensure_target_open(self,values,'payslip_id')
        return super().create(values_list)

    def write(self,values):
        ensure_target_open(self,values,'payslip_id')
        return super().write(values)

    def unlink(self):
        assert_mutable(self.mapped('payslip_id'))
        return super().unlink()


class Line(models.Model):
    _inherit='hr.payslip.line'

    @api.model_create_multi
    def create(self,values_list):
        for values in values_list:ensure_target_open(self,values,'slip_id')
        return super().create(values_list)

    def write(self,values):
        ensure_target_open(self,values,'slip_id')
        return super().write(values)

    def unlink(self):
        assert_mutable(self.mapped('slip_id'))
        return super().unlink()


class Structure(models.Model):
    _inherit='hr.payroll.structure'

    def _step_configuration_report(self):
        return configuration_report(self)

    def _step_validate_configuration(self):
        return validate_configuration(self)
