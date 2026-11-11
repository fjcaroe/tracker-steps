from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class FreightDispatchType(models.Model):
    _inherit = 'step.freight.dispatch.type'

    company_ids = fields.Many2many(
        'res.company', 'step_freight_dispatch_type_company_rel', 'dispatch_type_id', 'company_id',
        string='Empresas', default=lambda self: self.env.company,
        help='Deje vacío para que el tipo de despacho esté disponible en todas las empresas.',
    )

    def write(self, vals):
        if 'company_ids' in vals and not self.env.su and self.company_ids - self.env.user.company_ids:
            raise AccessError(_('Solo puede cambiar asignaciones de sus empresas autorizadas.'))
        return super().write(vals)

    @api.constrains('company_ids')
    def _check_dispatch_type_companies(self):
        for record in self:
            if not self.env.su and record.company_ids - self.env.user.company_ids:
                raise ValidationError(_('Seleccione empresas autorizadas para su usuario.'))
            if record.company_ids and self.env['step.dispatch.guide'].sudo().search_count([
                    ('dispatch_type_id', '=', record.id), ('company_id', 'not in', record.company_ids.ids),
            ], limit=1):
                raise ValidationError(_('Conserve las empresas de las guías que ya usan este tipo de despacho.'))


class DispatchGuide(models.Model):
    _inherit = 'step.dispatch.guide'

    @api.constrains('company_id', 'dispatch_type_id')
    def _check_dispatch_type_company(self):
        for guide in self:
            companies = guide.dispatch_type_id.company_ids
            if companies and guide.company_id not in companies:
                raise ValidationError(_('El tipo de despacho debe estar habilitado para la empresa de la guía.'))
