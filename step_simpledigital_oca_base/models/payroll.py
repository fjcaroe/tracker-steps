"""Functional model contracts for the actual Simple Digital provider on OCA."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class StructureType(models.Model):
    _inherit = 'hr.payroll.structure.type'
    default_struct_id = fields.Many2one('hr.payroll.structure', ondelete='restrict')


class Structure(models.Model):
    _inherit = 'hr.payroll.structure'
    note = fields.Html()
    use_worked_day_lines = fields.Boolean(default=True)
    input_line_type_ids = fields.Many2many('hr.payslip.input.type',
        'hr_payroll_structure_hr_payslip_input_type_rel','hr_payroll_structure_id','hr_payslip_input_type_id')


class Rule(models.Model):
    _inherit = 'hr.salary.rule'
    note = fields.Html()
    appears_on_employee_cost_dashboard = fields.Boolean(default=False)
    appears_on_payroll_report = fields.Boolean(default=False)


class RuleCategory(models.Model):
    _inherit = 'hr.salary.rule.category'
    note = fields.Html()


class WorkEntryType(models.Model):
    _inherit = 'hr.work.entry.type'
    unpaid_structure_ids = fields.Many2many('hr.payroll.structure',
        'hr_payroll_structure_hr_work_entry_type_rel','hr_work_entry_type_id','hr_payroll_structure_id')


class Contract(models.Model):
    _inherit = 'hr.contract'

    hourly_wage = fields.Monetary(string='Hourly wage', default=0)
    wage_type = fields.Selection([('monthly','Monthly'),('hourly','Hourly')],default='monthly')

    @api.onchange('structure_type_id')
    def _onchange_simpledigital_structure_type(self):
        for contract in self:
            if contract.structure_type_id.default_struct_id:
                contract.struct_id = contract.structure_type_id.default_struct_id


class WorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'
    currency_id = fields.Many2one(related='payslip_id.company_id.currency_id')
    is_paid = fields.Boolean(compute='_compute_payment')
    amount = fields.Monetary(compute='_compute_payment',currency_field='currency_id')

    @api.depends('number_of_days','contract_id.wage','work_entry_type_id.unpaid_structure_ids','payslip_id.struct_id')
    def _compute_payment(self):
        for line in self:
            line.is_paid = line.payslip_id.struct_id not in line.work_entry_type_id.unpaid_structure_ids
            if line.contract_id.schedule_pay not in (False,'monthly'):
                raise UserError(_('Only the audited monthly payroll basis is supported by this provider bridge.'))
            line.amount = line.contract_id.wage/30.0*line.number_of_days if line.is_paid else 0.0


class Payslip(models.Model):
    _inherit = 'hr.payslip'
    currency_id = fields.Many2one(related='company_id.currency_id')
    use_worked_day_lines = fields.Boolean(related='struct_id.use_worked_day_lines')
    paid_amount = fields.Monetary(compute='_compute_provider_totals',currency_field='currency_id')
    net_wage = fields.Monetary(compute='_compute_provider_totals',currency_field='currency_id')
    basic_wage = fields.Monetary(compute='_compute_provider_totals',currency_field='currency_id')
    gross_wage = fields.Monetary(compute='_compute_provider_totals',currency_field='currency_id')

    @api.depends('worked_days_line_ids.amount','line_ids.total','line_ids.code')
    def _compute_provider_totals(self):
        for slip in self:
            slip.paid_amount = sum(slip.worked_days_line_ids.mapped('amount'))
            totals = slip._get_line_values(['BASIC','GROSS','NET'])
            slip.basic_wage = totals['BASIC'][slip.id]['total']
            slip.gross_wage = totals['GROSS'][slip.id]['total']
            slip.net_wage = totals['NET'][slip.id]['total']


class PayslipLine(models.Model):
    _inherit = 'hr.payslip.line'
    condition_python = fields.Text(groups='payroll.group_payroll_user')
    condition_range = fields.Char(groups='payroll.group_payroll_user')
    amount_python_compute = fields.Text(groups='payroll.group_payroll_user')
    amount_percentage_base = fields.Char(groups='payroll.group_payroll_user')
