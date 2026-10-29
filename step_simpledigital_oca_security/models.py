"""Require country-specific data at payroll processing, never invent old master data."""
from odoo import api, models, _
from odoo.addons.step_payroll_contracts.history import assert_mutable, history_protected
from odoo.addons.step_payroll_contracts.configuration import configuration_report, validate_configuration
from odoo.exceptions import UserError


class Payslip(models.Model):
    _inherit = 'hr.payslip'

    def _step_require_open_wage_basis(self):
        """Live contract helpers are calculation APIs, never historical snapshots."""
        self.ensure_one()
        self.check_access('read')
        if history_protected(self):
            raise UserError(_('Closed payroll has no certified stored wage basis for this calculation. '
                              'Read its original stored payroll totals instead; no current contract wage will be used.'))

    def _get_contract_wage(self):
        self._step_require_open_wage_basis()
        return super()._get_contract_wage()

    def _get_paid_amount(self):
        self._step_require_open_wage_basis()
        return super()._get_paid_amount()

    def _get_unpaid_amount(self):
        self._step_require_open_wage_basis()
        return super()._get_unpaid_amount()

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

    def _step_check_country_calculation_configuration(self):
        if any(slip.state not in ('draft','verify') or ('paid' in slip._fields and slip.paid) for slip in self):
            raise UserError(_('Validated or paid payroll cannot be recalculated.'))
        for slip in self:
            roots=slip._step_selected_payroll_structures() if hasattr(slip,'_step_selected_payroll_structures') else slip.struct_id
            chile=self.env['hr.payroll.structure']
            for root in roots:
                hierarchy=root._step_effective_rule_scope()['structures'] if hasattr(root,'_step_effective_rule_scope') else root
                if hierarchy.filtered(lambda structure:structure.name=='Nómina Chile'):
                    chile |= root
            if not chile:
                continue
            reports={structure.id:validate_configuration(structure) for structure in chile}
            # Provider Chile helpers are defined on an explicit payslip profile
            # and contract. Diagnose the real fallback first, then refuse an
            # uncertified implicit context instead of assigning new masters.
            if not slip.struct_id or slip.struct_id.name!='Nómina Chile' or not slip.contract_id:
                raise UserError(_('Select the original Chile payroll structure and contract explicitly before calculation.'))
            report=reports[slip.struct_id.id]
            contract=slip.contract_id
            missing=[field for field in ('contract_type_id','analytic_account_id','health_institution','pension_option','income_tax_type','work_schedule_id') if not contract[field]]
            for field in ('hr_commune','identification_id','country_id','birthday','gender'):
                if not slip.employee_id[field]:missing.append(field)
            if missing:
                raise UserError(_('Complete Chile payroll data before calculation: %s',', '.join(missing)))
            if not {'BASIC','GROSS','NET'} <= set(report['essential_ids']):
                raise UserError(_('Adopt the original base, gross and net rules before processing Chile payroll.'))
            if not contract.get_work_hours(slip.date_from,slip.date_to):
                raise UserError(_('Generate actual work entries before calculating Chile payroll.'))
            if contract.wage_type!='monthly' or contract.schedule_pay!='monthly':
                raise UserError(_('This provider rehearsal supports audited monthly wage payroll only.'))
        return True

    def compute_sheet(self):
        self._step_check_country_calculation_configuration()
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
