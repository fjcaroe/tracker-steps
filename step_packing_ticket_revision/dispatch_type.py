from odoo import _, api, models
from odoo.exceptions import ValidationError


class DispatchGuide(models.Model):
    _inherit = 'step.dispatch.guide'

    @api.constrains('company_id', 'dispatch_type_id')
    def _check_dispatch_type_company(self):
        for guide in self:
            companies = guide.dispatch_type_id.company_ids
            if companies and guide.company_id not in companies:
                raise ValidationError(_('El tipo de despacho debe estar habilitado para la empresa de la guía.'))
