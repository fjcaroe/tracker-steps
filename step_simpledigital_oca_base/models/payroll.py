"""Functional model contracts for the actual Simple Digital provider on OCA."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons.step_payroll_contracts.history import history_protected, restore_snapshot_cache


class StructureType(models.Model):
    _inherit = 'hr.payroll.structure.type'
    default_struct_id = fields.Many2one('hr.payroll.structure', ondelete='set null')


class Structure(models.Model):
    _inherit = 'hr.payroll.structure'
    note = fields.Html()
    use_worked_day_lines = fields.Boolean(default=True)
    input_line_type_ids = fields.Many2many('hr.payslip.input.type',
        'hr_payroll_structure_hr_payslip_input_type_rel','hr_payroll_structure_id','hr_payslip_input_type_id',copy=False)

    @api.model_create_multi
    def create(self,values_list):
        used=self.env['hr.payslip.input.type']
        if any('input_line_type_ids' in values for values in values_list):
            used=self.env['hr.payslip.input'].sudo().search([('input_type_id','!=',False)]).mapped('input_type_id')
        original={kind.id:set(kind.struct_ids.ids) for kind in used}
        with self.env.cr.savepoint():
            result=super().create(values_list)
            if any(set(kind.struct_ids.ids)!=original[kind.id] for kind in used):
                raise ValidationError(_('Used input types retain their historical structure scope.'))
            return result

    def write(self,values):
        used=self.env['hr.payslip.input.type']
        if 'input_line_type_ids' in values:
            used=self.env['hr.payslip.input'].sudo().search([('input_type_id','!=',False)]).mapped('input_type_id')
        original={kind.id:set(kind.struct_ids.ids) for kind in used}
        with self.env.cr.savepoint():
            result=super().write(values)
            if any(set(kind.struct_ids.ids)!=original[kind.id] for kind in used):
                raise ValidationError(_('Used input types retain their historical structure scope.'))
            return result


class Rule(models.Model):
    _inherit = 'hr.salary.rule'
    note = fields.Html(translate=True)

    def write(self,values):
        if self._name=='hr.salary.rule' and 'code' in values and any(rule.code!=values['code'] for rule in self):
            used=self.env['hr.payslip.line'].sudo().search_count([
                ('salary_rule_id','in',self.ids),'|',('slip_id.step_history_locked','=',True),
                '|',('slip_id.paid','=',True),('slip_id.state','not in',('draft','verify'))])
            if used:
                raise UserError(_('Codes used in closed payroll retain their historical identity. Create a new rule.'))
        return super().write(values)

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
    is_paid = fields.Boolean(compute='_compute_payment',store=True)
    amount = fields.Monetary(compute='_compute_payment',currency_field='currency_id',store=True)

    @api.depends('number_of_days','contract_id.wage','work_entry_type_id.unpaid_structure_ids','payslip_id.struct_id')
    def _compute_payment(self):
        frozen=self.filtered(lambda line:history_protected(line.payslip_id))
        restore_snapshot_cache(frozen)
        for line in self-frozen:
            line.is_paid = line.payslip_id.struct_id not in line.work_entry_type_id.unpaid_structure_ids
            if line.contract_id.schedule_pay not in (False,'monthly'):
                raise UserError(_('Only the audited monthly payroll basis is supported by this provider bridge.'))
            line.amount = line.contract_id.wage/30.0*line.number_of_days if line.is_paid else 0.0


class Payslip(models.Model):
    _inherit = 'hr.payslip'
    currency_id = fields.Many2one(related='company_id.currency_id')
    use_worked_day_lines = fields.Boolean(related='struct_id.use_worked_day_lines')
    net_wage = fields.Monetary(compute='_compute_provider_totals',currency_field='currency_id',store=True)
    basic_wage = fields.Monetary(compute='_compute_provider_totals',currency_field='currency_id',store=True)
    gross_wage = fields.Monetary(compute='_compute_provider_totals',currency_field='currency_id',store=True)

    step_history_locked = fields.Boolean(string='Liquidación cerrada',default=False,copy=False,readonly=True)

    @api.model_create_multi
    def create(self,values_list):
        for values in values_list:
            if values.get('state','draft') not in ('draft','verify') or values.get('paid') or values.get('step_history_locked'):
                raise UserError(_('Create draft payroll normally; import closed history through the audited migration.'))
        return super().create(values_list)

    def write(self,values):
        if 'step_history_locked' in values:
            raise UserError(_('The payroll history lock is managed by validation.'))
        closing=(values.get('paid') or ('state' in values and values['state'] not in ('draft','verify')))
        if closing:
            if {'employee_id','company_id','contract_id','struct_id','date_from','date_to','line_ids','input_line_ids','worked_days_line_ids'} & values.keys():
                raise UserError(_('Update the draft payroll context before closing its stored amounts.'))
            # Materialize while still draft; never derive a closed snapshot from today's wage.
            self.mapped('worked_days_line_ids').flush_recordset(['amount','is_paid'])
            self.flush_recordset(['basic_wage','gross_wage','net_wage'])
        if values.get('paid') or values.get('state') in ('done','paid'):
            values=dict(values,step_history_locked=True)
        return super().write(values)

    def compute_sheet(self):
        if any(history_protected(slip) for slip in self):
            raise UserError(_('Closed payroll history cannot be recalculated.'))
        return super().compute_sheet()

    @property
    def paid_amount(self):
        return self._get_paid_amount()

    def _get_contract_wage(self):
        self.ensure_one();self.check_access('read')
        if self.contract_id.wage_type!='monthly' or self.contract_id.schedule_pay!='monthly':
            raise UserError(_('This provider bridge supports audited monthly wages only.'))
        return self.contract_id.wage

    def _get_paid_amount(self):
        self.ensure_one();self.check_access('read')
        if self.env.context.get('no_paid_amount'):
            return 0.0
        if self.env.context.get('salary_simulation'):
            raise UserError(_('Salary simulation requires a separate certified payroll contract.'))
        if not self.use_worked_day_lines:
            return self._get_contract_wage()
        self.worked_days_line_ids.check_access('read')
        return sum(self.worked_days_line_ids.mapped('amount'))

    def _get_unpaid_amount(self):
        return self._get_contract_wage()-self._get_paid_amount()

    @api.depends('line_ids.total','line_ids.code')
    def _compute_provider_totals(self):
        frozen=self.filtered(history_protected)
        restore_snapshot_cache(frozen)
        for slip in self-frozen:
            totals = slip._get_line_values(['BASIC','GROSS','NET'])
            slip.basic_wage = totals['BASIC'][slip.id]['total']
            slip.gross_wage = totals['GROSS'][slip.id]['total']
            slip.net_wage = totals['NET'][slip.id]['total']


class PayslipLine(models.Model):
    _inherit = 'hr.payslip.line'
    # Preserve the actual mandatory native related-code contract.
    code = fields.Char(required=True)
    condition_python = fields.Text(groups='payroll.group_payroll_user')
    condition_range = fields.Char(groups='payroll.group_payroll_user')
    amount_python_compute = fields.Text(groups='payroll.group_payroll_user')
    amount_percentage_base = fields.Char(groups='payroll.group_payroll_user')
