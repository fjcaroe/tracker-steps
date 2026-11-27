from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class Category(models.Model):
    _name = 'step.management.fruit.category'
    _inherit = ['step.management.fruit.category', 'step.shared.agriculture.master']
    company_ids = fields.Many2many('res.company', 'step_fruit_category_company_rel', 'master_id', 'company_id', string='Empresas y sucursales', required=True, default=lambda self: self.env.company)

    def write(self, vals):
        result = super().write(vals)
        if 'company_ids' in vals:
            self.env['step.management.fruit.class'].sudo().search([('category_id', 'in', self.ids)])._check_category_memberships()
        return result


class FruitClass(models.Model):
    _name = 'step.management.fruit.class'
    _inherit = ['step.management.fruit.class', 'step.shared.agriculture.master']
    company_ids = fields.Many2many('res.company', 'step_fruit_class_company_rel', 'master_id', 'company_id', string='Empresas y sucursales', required=True, default=lambda self: self.env.company)

    @api.constrains('company_ids', 'category_id')
    def _check_category_memberships(self):
        for record in self:
            if record.company_ids - record.category_id.company_ids:
                raise ValidationError(_('La categoría debe estar disponible en todas las empresas seleccionadas para la clase.'))
