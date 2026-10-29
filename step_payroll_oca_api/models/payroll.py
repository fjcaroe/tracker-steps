"""Data/API compatibility on the real OCA engine; no replacement payslip model.

No Chilean rate policy or historical migration is implemented here.
"""
from datetime import date

from odoo.tools.float_utils import float_round
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons.step_payroll_contracts.history import assert_mutable
from odoo.addons.payroll.models.base_browsable import WorkedDays, InputLine, BaseBrowsableObject


class Structure(models.Model):
    _inherit = 'hr.payroll.structure'

    type_id = fields.Many2one('hr.payroll.structure.type', string='Type', ondelete='restrict')
    step_clp_concept_rounding = fields.Boolean(string='Redondear conceptos en pesos (Chile)',
        help='Redondea cada concepto antes de acumular categorías desde octubre de 2026. No modifica liquidaciones validadas.')

    def _step_rule_membership_access(self, commands=()):
        """Authorize physical memberships and primary FKs, including archives.

        Visibility is checked before editing; consistency afterwards. This
        allows an authorized explicit repair without hiding an original rule
        behind a filtered search or a warm/sudo relation cache.
        """
        normal = self.sudo(False).with_context(active_test=False)
        normal.check_access('read')
        normal.check_field_access_rights('read', ['rule_ids'])
        rules = normal.env['hr.salary.rule'].with_context(active_test=False)
        rules.check_access('read')
        rules.check_field_access_rights('read', ['struct_id'])
        rules.flush_model(['struct_id'])
        normal.flush_recordset(['rule_ids'])
        normal.env.cr.execute('SELECT struct_id,rule_id FROM hr_structure_salary_rule_rel WHERE struct_id=ANY(%s)', (normal.ids,))
        pairs = set(normal.env.cr.fetchall())
        normal.env.cr.execute('SELECT id,struct_id FROM hr_salary_rule WHERE struct_id=ANY(%s)', (normal.ids,))
        primary = normal.env.cr.fetchall()
        ids = {rule_id for struct_id, rule_id in pairs} | {rule_id for rule_id, struct_id in primary}
        if getattr(commands, '_name', None) == 'hr.salary.rule':
            ids.update(commands.ids)
        else:
            for command in commands or ():
                if type(command) is int:
                    ids.add(command)
                elif isinstance(command, (tuple, list)) and command:
                    if command[0] in (1, 2, 3, 4) and len(command) > 1 and command[1]:
                        ids.add(command[1])
                    elif command[0] == 6 and len(command) > 2:
                        ids.update(command[2])
        original = rules.browse(sorted(ids))
        original.check_access('read')
        if set(original.exists().ids) != ids:
            raise ValidationError(_('Select existing original salary-rule references.'))
        return pairs, primary

    @api.model_create_multi
    def create(self, vals_list):
        if not any('rule_ids' in values for values in vals_list) and 'default_rule_ids' not in self.env.context:
            return super().create(vals_list)
        normal = self.sudo(False)
        normal.check_access('create')
        normal.check_field_access_rights('write', ['rule_ids'])
        for values in vals_list:
            normal._step_rule_membership_access(values.get('rule_ids', normal.env.context.get('default_rule_ids', ())))
        with normal.env.cr.savepoint():
            records = super(Structure, normal).create(vals_list)
            records._check_primary_rule_membership()
            return records

    def write(self, values):
        if 'rule_ids' not in values:
            return super().write(values)
        normal = self.sudo(False)
        normal.check_access('write')
        normal.check_field_access_rights('write', ['rule_ids'])
        normal._step_rule_membership_access(values['rule_ids'])
        with normal.env.cr.savepoint():
            result = super(Structure, normal).write(values)
            normal._check_primary_rule_membership()
            return result

    @api.constrains('rule_ids')
    def _check_primary_rule_membership(self):
        pairs, primary = self._step_rule_membership_access()
        if any((structure_id, rule_id) not in pairs for rule_id, structure_id in primary):
            raise ValidationError(_('Move the rule primary structure before removing its membership.'))


class Rule(models.Model):
    _inherit = 'hr.salary.rule'

    struct_id = fields.Many2one('hr.payroll.structure', string='Salary Structure', ondelete='restrict')

    @api.model_create_multi
    def create(self, vals_list):
        if self._name != 'hr.salary.rule':
            return super().create(vals_list)
        normal = self.sudo(False)
        normal.check_access('create')
        with normal.env.cr.savepoint():
            records = super(Rule, normal).create(vals_list)
            records._link_original_structure()
            records._step_check_primary_membership()
            return records

    def write(self, values):
        if self._name != 'hr.salary.rule':
            return super().write(values)
        normal = self.sudo(False)
        normal.check_access('write')
        normal.check_field_access_rights('write', list(values))
        if not {'struct_id', 'company_id'} & values.keys():
            return super(Rule, normal).write(values)
        normal._step_rule_owner_references()
        old = {rule.id: rule.struct_id for rule in normal} if 'struct_id' in values else {}
        if values.get('struct_id'):
            target_id = normal._fields['struct_id'].convert_to_cache(values['struct_id'], normal)
            target = normal.env['hr.payroll.structure'].browse(target_id)
            target.check_access('read')
            target.check_field_access_rights('read', ['company_id', 'rule_ids'])
        with normal.env.cr.savepoint():
            result = super(Rule, normal).write(values)
            for rule in normal:
                if old.get(rule.id) and old[rule.id] != rule.struct_id:
                    old[rule.id].write({'rule_ids': [fields.Command.unlink(rule.id)]})
            if 'struct_id' in values:
                normal._link_original_structure()
            normal._step_check_primary_membership()
            return result

    def _step_rule_owner_references(self):
        if self._name != 'hr.salary.rule':
            return self.env['hr.payroll.structure']
        normal = self.sudo(False)
        normal.check_access('read')
        normal.check_field_access_rights('read', ['struct_id', 'company_id'])
        structures = normal.struct_id
        structures.check_access('read')
        structures.check_field_access_rights('read', ['company_id', 'rule_ids'])
        normal.company_id.check_access('read')
        structures.company_id.check_access('read')
        return structures

    def _step_check_primary_membership(self):
        if self._name != 'hr.salary.rule':
            return
        normal = self.sudo(False)
        structures = normal._step_rule_owner_references()
        normal.flush_recordset(['struct_id'])
        structures.flush_recordset(['rule_ids'])
        normal.env.cr.execute('SELECT rule_id,struct_id FROM hr_structure_salary_rule_rel WHERE rule_id=ANY(%s)', (normal.ids,))
        pairs = set(normal.env.cr.fetchall())
        if any(rule.struct_id and (rule.id, rule.struct_id.id) not in pairs for rule in normal):
            raise ValidationError(_('Move the rule primary structure before removing its membership.'))

    @api.constrains('company_id','struct_id')
    def _check_structure_company(self):
        if self._name != 'hr.salary.rule':
            return
        normal = self.sudo(False)
        normal._step_rule_owner_references()
        for rule in normal.filtered('struct_id'):
            if rule.company_id and rule.struct_id.company_id != rule.company_id:
                raise ValidationError(_('Rule and structure must belong to the same company.'))

    def _link_original_structure(self):
        if self._name != 'hr.salary.rule':
            return
        normal = self.sudo(False)
        normal._step_rule_owner_references()
        for rule in normal.filtered('struct_id'):
            if rule.company_id and rule.struct_id.company_id != rule.company_id:
                raise ValidationError(_('Rule and structure must belong to the same company.'))
            if rule not in rule.struct_id.rule_ids:
                rule.struct_id.write({'rule_ids':[fields.Command.link(rule.id)]})


class InputType(models.Model):
    _name = 'hr.payslip.input.type'
    _description = 'Payroll input type'

    name = fields.Char(required=True, translate=False)
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
            # Existence only: protect global types even under another company's rules.
            used=self.env['hr.payslip.input'].sudo().search_count([('input_type_id','in',self.ids)])
            if used:
                raise ValidationError(_('Used input types retain their code, country and structure scope. Create a new type.'))
        return super().write(values)

    @api.constrains('code','country_id','struct_ids','active')
    def _check_code_scope(self):
        self.flush_model(['code','country_id','active','struct_ids'])
        for record in self.filtered('active'):
            # A country rule may hide an overlapping global-code candidate.
            # Read IDs only, then require normal access before qualification.
            self.env.cr.execute("""SELECT id FROM hr_payslip_input_type
                WHERE id!=%s AND code=%s AND active
                AND (country_id IS NULL OR %s IS NULL OR country_id=%s)""",
                (record.id,record.code,record.country_id.id or None,record.country_id.id or None))
            others=self.browse([row[0] for row in self.env.cr.fetchall()])
            others.check_access('read')
            if others.filtered(lambda other: (not other.country_id or not record.country_id or other.country_id==record.country_id)
                    and (not other.struct_ids or not record.struct_ids or bool(other.struct_ids & record.struct_ids))):
                raise ValidationError(_('Input code is ambiguous for this country/structure.'))


class Input(models.Model):
    _inherit = 'hr.payslip.input'

    # Native historical inputs can have no label. Retain that SQL NULL instead
    # of inventing a description from today's mutable master during adoption.
    name = fields.Char(required=False)
    input_type_id = fields.Many2one('hr.payslip.input.type', ondelete='restrict')

    @api.model_create_multi
    def create(self, vals_list):
        prepared=[]
        for values in vals_list:
            values=dict(values)
            if values.get('payslip_id'):
                slip=self.env['hr.payslip'].browse(values['payslip_id'])
                assert_mutable(slip)
                if values.get('input_type_id') and 'contract_id' not in values:
                    values['contract_id']=slip.contract_id.id
            if values.get('input_type_id'):
                kind=self.env['hr.payslip.input.type'].browse(values['input_type_id'])
                if values.get('code') and values['code'] != kind.code:
                    raise ValidationError(_('Input code does not match its type.'))
                values['code']=kind.code
                values.setdefault('name',kind.name)
            prepared.append(values)
        return super().create(prepared)

    def write(self, values):
        assert_mutable(self.mapped('payslip_id'))
        if values.get('payslip_id'):
            assert_mutable(self.env['hr.payslip'].browse(values['payslip_id']))
        if 'input_type_id' in values and not values['input_type_id'] and self.input_type_id:
            raise ValidationError(_('A typed input must retain its master relation.'))
        if 'input_type_id' in values and values['input_type_id']:
            code=self.env['hr.payslip.input.type'].browse(values['input_type_id']).code
            if values.get('code') and values['code'] != code:
                raise ValidationError(_('Input code does not match its type.'))
            values=dict(values,code=code)
        return super().write(values)

    def unlink(self):
        assert_mutable(self.mapped('payslip_id'))
        return super().unlink()

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
            if line.contract_id != slip.contract_id or line.contract_id.employee_id != slip.employee_id or line.contract_id.company_id != slip.company_id:
                raise ValidationError(_('Input must retain the payslip employee and company contract.'))


class InputAmountGroup:
    """Rule context over real inputs, with additive amounts and original row IDs."""
    def __init__(self, records):
        self.records = records

    @property
    def amount(self):
        return sum(self.records.mapped('amount'))

    def __getattr__(self, name):
        return getattr(self.records, name)

    def __bool__(self):
        return bool(self.records)


class ValueMapping(BaseBrowsableObject):
    def __getitem__(self, code):
        return self.dict[code]

    def get(self, code, default=None):
        return self.dict.get(code, default)


class CategoryMapping(ValueMapping):
    def __getitem__(self, code):
        return self.dict.get(code, 0.0)


class InputLineMapping(InputLine):
    def __getitem__(self, code):
        return self.dict[code]

    def get(self, code, default=None):
        return self.dict.get(code, default)


class WorkedDaysMapping(WorkedDays):
    def get(self, code, default=None):
        return self.dict.get(code, default)


def preserve_paid_state(records):
    if records:
        raise UserError(_('Adopt original paid state identity before removing this API.'))


class Payslip(models.Model):
    _inherit = 'hr.payslip'

    state = fields.Selection(selection_add=[('paid','Paid'),('cancel',)],
        ondelete={'paid':preserve_paid_state})

    def _get_salary_rules(self):
        # A same-sequence rule retains its original ID tie-breaker after import.
        # Never use new XML IDs or M2M insertion order to resolve legacy rules.
        return super()._get_salary_rules().sorted(lambda rule: (rule.sequence, rule.id))

    def _get_baselocaldict(self, contracts):
        result=super()._get_baselocaldict(contracts)
        grouped = self.input_line_ids.grouped('code')
        inputs = dict(result['inputs'].dict)
        for code, lines in grouped.items():
            if len(lines)>1 and lines.input_type_id:
                if len(lines.input_type_id)!=1 or any(not line.input_type_id for line in lines):
                    raise UserError(_('Repeated input codes must use the same explicit input type.'))
                inputs[code] = InputAmountGroup(lines)
        result['inputs']=InputLineMapping(self.employee_id.id,inputs,self.env)
        result['result_rules']=ValueMapping(result['result_rules'].dict)
        result['categories']=CategoryMapping(result['categories'].dict)
        result['worked_days']=WorkedDaysMapping(self.employee_id.id,
            {line.code:line for line in self.worked_days_line_ids if line.code},self.env)
        return result

    def _step_clp_rounding_applies(self):
        self.ensure_one()
        chile_type = self.env.ref('l10n_cl_simpledigital_payroll.structure_type_chile', raise_if_not_found=False)
        configured = self.struct_id.step_clp_concept_rounding or (chile_type and self.struct_id.type_id == chile_type)
        return bool(configured and self.company_id.currency_id.name == 'CLP'
                    and self.date_from and self.date_from >= date(2026,10,1)
                    and self.state in ('draft','verify'))

    def _get_payslip_line_total(self, amount, quantity, rate, rule):
        total = amount*quantity*rate/100.0
        return float_round(total, precision_digits=0, rounding_method='HALF-UP') if self._step_clp_rounding_applies() else total

    def _get_lines_dict(self, rule, localdict, lines_dict, key, values, previous_amount):
        localdict, lines_dict = super()._get_lines_dict(rule,localdict,lines_dict,key,values,previous_amount)
        if self._step_clp_rounding_applies():
            line = lines_dict[key]
            total = self._get_payslip_line_total(values['amount'],values['quantity'],values['rate'],rule)
            correction = total-line['total']
            self._sum_salary_rule_category(localdict,rule.category_id,correction)
            line['total'] = total
            if rule.code:
                localdict[rule.code] = total
                localdict['result_rules'].dict[rule.code].dict['total'] = total
        return localdict, lines_dict

    def _compute_payslip_line(self, rule, localdict, lines_dict):
        group = localdict['inputs'].get(rule.code)
        if not isinstance(group, InputAmountGroup):
            result = super()._compute_payslip_line(rule, localdict, lines_dict)
            values = localdict['result_rules'].dict.get(rule.code)
            if values is not None:
                localdict['result_rules'].dict[rule.code] = ValueMapping(values.dict)
            return result
        # Evaluate nonlinear and quantity rules per actual input, retaining each row.
        original = localdict.get(rule.code)
        total = 0.0
        try:
            for line in group.records:
                localdict['inputs'].dict[rule.code] = line
                localdict[rule.code] = 0.0
                localdict.update(result=None, result_qty=1.0, result_rate=100.0, result_name=False)
                super()._compute_payslip_line(rule, localdict, lines_dict)
                key = rule.code+'-'+str(localdict['contract'].id)
                values = lines_dict.pop(key)
                total += values['total']
                lines_dict[key+'-input-'+str(line.id)] = values
        finally:
            localdict['inputs'].dict[rule.code] = group
            if original is None:
                localdict.pop(rule.code, None)
            else:
                localdict[rule.code] = original
        localdict['result_rules'].dict[rule.code] = ValueMapping(
            {'total': total, 'amount': total, 'quantity': 1.0, 'rate': 100.0})
        return localdict, lines_dict

    @api.constrains('struct_id','employee_id','company_id','contract_id')
    def _check_existing_typed_inputs(self):
        self.mapped('input_line_ids')._check_typed_input()

    def compute_sheet(self):
        if any(slip.paid or slip.state not in ('draft','verify') for slip in self):
            raise UserError(_('Validated or paid payroll cannot be recalculated.'))
        self.mapped('input_line_ids')._check_typed_input()
        for slip in self:
            for lines in slip.input_line_ids.grouped('code').values():
                if len(lines)>1 and lines.input_type_id and (
                        len(lines.input_type_id)!=1 or any(not line.input_type_id for line in lines)):
                    raise UserError(_('Repeated input codes must use the same explicit input type.'))
        return super().compute_sheet()

    def get_salary_line_total(self, code):
        self.ensure_one()
        self.check_access('read')
        lines = self.line_ids.filtered(lambda line:line.code==code)
        # Native OCA assumes one line per code. Typed repeated inputs now retain
        # several real lines; its legacy total helper must read all those lines.
        if len(lines)>1 and self.input_line_ids.filtered(lambda line:line.code==code and line.input_type_id):
            lines.check_access('read')
            return sum(lines.mapped('total'))
        return super().get_salary_line_total(code)

    def _get_line_values(self, code_list, vals_list=None, compute_sum=False):
        self.check_access('read')
        values=vals_list or ['total']
        if set(values)-{'amount','quantity','total','ytd'}:
            raise UserError(_('Unsupported payroll line value.'))
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
