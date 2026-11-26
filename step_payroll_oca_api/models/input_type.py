from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


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
