from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class HarvestTag(models.Model):
    _inherit = 'step.agriculture.harvest.tag'

    # Keep the original column and FK as evidence, rather than replacing its
    # values with IDs from a different master. The operational relation reuses
    # the existing Packing master approved by the user.
    tag_state_id = fields.Many2one(string='Estado original de tarja', readonly=True, copy=False)
    packing_tag_state_id = fields.Many2one(
        'step.packing.tag.state', string='Estado tarja', ondelete='restrict',
        domain=lambda self: [('company_id', 'in', [False, *self.env.companies.ids])])

    @api.model_create_multi
    def create(self, values_list):
        if any(values.get('tag_state_id') for values in values_list):
            raise UserError(_('El estado original se conserva como referencia de solo lectura.'))
        return super().create(values_list)

    def write(self, values):
        if 'tag_state_id' in values:
            raise UserError(_('El estado original se conserva como referencia de solo lectura.'))
        return super().write(values)

    @api.constrains('packing_tag_state_id', 'harvest_id')
    def _check_state_company(self):
        for tag in self:
            owner = tag.harvest_id.cost_center_id.company_id
            company = tag.packing_tag_state_id.company_id
            if owner and company and owner != company:
                raise ValidationError(_('El estado de tarja debe pertenecer a la empresa del centro de costo.'))


class OriginalTagState(models.Model):
    _inherit = 'step.agriculture.harvest.tag.state'
    _description = 'Estados originales de tarja (histórico)'

    @api.model_create_multi
    def create(self, values_list):
        raise UserError(_('Los estados originales se conservan únicamente como histórico.'))

    def write(self, values):
        raise UserError(_('Los estados originales se conservan únicamente como histórico.'))

    def unlink(self):
        raise UserError(_('Los estados originales se conservan únicamente como histórico.'))
