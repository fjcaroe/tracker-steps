"""Data/API compatibility on the real OCA engine; no replacement payslip model.

No Chilean rate policy or historical migration is implemented here.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons.payroll.models.base_browsable import WorkedDays


class Structure(models.Model):
    _inherit = 'hr.payroll.structure'

    type_id = fields.Many2one('hr.payroll.structure.type', string='Type', ondelete='restrict')

    @api.constrains('rule_ids')
    def _check_primary_rule_membership(self):
        for structure in self:
            primary=self.env['hr.salary.rule'].search([('struct_id','=',structure.id)])
            if primary-structure.rule_ids:
                raise ValidationError(_('Move the rule primary structure before removing its membership.'))


class Rule(models.Model):
    _inherit = 'hr.salary.rule'

    struct_id = fields.Many2one('hr.payroll.structure', string='Salary Structure', ondelete='restrict')

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._link_original_structure()
        return records

    def write(self, values):
        old = {rule.id:rule.struct_id for rule in self} if 'struct_id' in values else {}
        result = super().write(values)
        for rule in self:
            if rule.id in old and old[rule.id] and old[rule.id] != rule.struct_id:
                old[rule.id].write({'rule_ids': [fields.Command.unlink(rule.id)]})
        if 'struct_id' in values:
            self._link_original_structure()
        return result

    def _link_original_structure(self):
        for rule in self.filtered('struct_id'):
            if rule.company_id and rule.struct_id.company_id != rule.company_id:
                raise ValidationError(_('Rule and structure must belong to the same company.'))
            if rule not in rule.struct_id.rule_ids:
                rule.struct_id.write({'rule_ids':[fields.Command.link(rule.id)]})


class InputType(models.Model):
    _name = 'hr.payslip.input.type'
    _description = 'Payroll input type'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    active = fields.Boolean(default=True)
    country_id = fields.Many2one('res.country', default=lambda self:self.env.company.country_id)
    country_code = fields.Char(related='country_id.code')
    struct_ids = fields.Many2many('hr.payroll.structure',
        'hr_payroll_structure_hr_payslip_input_type_rel', 'hr_payslip_input_type_id', 'hr_payroll_structure_id')
    is_quantity = fields.Boolean()
    available_in_attachments = fields.Boolean()
    default_no_end_date = fields.Boolean()

    def write(self, values):
        if {'code','country_id','struct_ids'} & values.keys():
            used=self.env['hr.payslip.input'].search_count([('input_type_id','in',self.ids)])
            if used:
                raise ValidationError(_('Used input types retain their code, country and structure scope. Create a new type.'))
        return super().write(values)

    @api.constrains('code','country_id','struct_ids','active')
    def _check_code_scope(self):
        for record in self.filtered('active'):
            others=self.search([('id','!=',record.id),('code','=',record.code)])
            if others.filtered(lambda other: (not other.country_id or not record.country_id or other.country_id==record.country_id)
                    and (not other.struct_ids or not record.struct_ids or bool(other.struct_ids & record.struct_ids))):
                raise ValidationError(_('Input code is ambiguous for this country/structure.'))


class Input(models.Model):
    _inherit = 'hr.payslip.input'

    input_type_id = fields.Many2one('hr.payslip.input.type', ondelete='restrict')

    @api.model_create_multi
    def create(self, vals_list):
        prepared=[]
        for values in vals_list:
            values=dict(values)
            if values.get('input_type_id'):
                kind=self.env['hr.payslip.input.type'].browse(values['input_type_id'])
                if values.get('code') and values['code'] != kind.code:
                    raise ValidationError(_('Input code does not match its type.'))
                values['code']=kind.code
                values.setdefault('name',kind.name)
            prepared.append(values)
        return super().create(prepared)

    def write(self, values):
        if 'input_type_id' in values and values['input_type_id']:
            code=self.env['hr.payslip.input.type'].browse(values['input_type_id']).code
            if values.get('code') and values['code'] != code:
                raise ValidationError(_('Input code does not match its type.'))
            values=dict(values,code=code)
        return super().write(values)

    @api.constrains('input_type_id','code','payslip_id','contract_id')
    def _check_typed_input(self):
        for line in self.filtered('input_type_id'):
            kind=line.input_type_id;slip=line.payslip_id
            if not kind.active or line.code != kind.code:
                raise ValidationError(_('Input type must be active and match the code.'))
            if kind.struct_ids and slip.struct_id not in kind.struct_ids:
                raise ValidationError(_('Input type is not available for this structure.'))
            if kind.country_id and kind.country_id != slip.company_id.country_id:
                raise ValidationError(_('Input type belongs to another country.'))
            if line.contract_id.employee_id != slip.employee_id or line.contract_id.company_id != slip.company_id:
                raise ValidationError(_('Input must retain the payslip employee and company contract.'))


class WorkedDaysMapping(WorkedDays):
    def get(self, code, default=None):
        return self.dict.get(code, default)


class Payslip(models.Model):
    _inherit = 'hr.payslip'

    def _get_baselocaldict(self, contracts):
        result=super()._get_baselocaldict(contracts)
        result['worked_days']=WorkedDaysMapping(self.employee_id.id,
            {line.code:line for line in self.worked_days_line_ids if line.code},self.env)
        return result

    def compute_sheet(self):
        if any(slip.paid or slip.state not in ('draft','verify') for slip in self):
            raise UserError(_('Validated or paid payroll cannot be recalculated.'))
        return super().compute_sheet()

    def _get_line_values(self, code_list, vals_list=None, compute_sum=False):
        self.check_access('read')
        values=vals_list or ['total']
        if set(values)-{'amount','quantity','total'}:
            raise UserError(_('Unsupported payroll values; YTD requires a separately validated implementation.'))
        result={code:{slip.id:{value:0.0 for value in values} for slip in self} for code in code_list}
        lines=self.mapped('line_ids').filtered(lambda line:line.code in result)
        lines.check_access('read')
        for line in lines:
            for value in values:
                result[line.code][line.slip_id.id][value]+=line[value]
        if compute_sum:
            for data in result.values():
                data['sum']={value:sum(row[value] for row in data.values()) for value in values}
        return result
