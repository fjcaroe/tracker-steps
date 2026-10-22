from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HarvestTag(models.Model):
    _inherit = 'step.agriculture.harvest.tag'

    tag_state_id = fields.Many2one(
        'step.packing.tag.state', string='Estado de tarja',
        domain=lambda self: [('company_id', 'in', [False, *self.env.companies.ids])])

    @api.model_create_multi
    def create(self, values_list):
        if any(values.get('legacy_tag_state_id') for values in values_list):
            raise UserError(_('El estado histórico se conserva como referencia de solo lectura.'))
        return super().create(values_list)

    def write(self, values):
        if 'legacy_tag_state_id' in values and any(record.legacy_tag_state_id.id != values['legacy_tag_state_id'] for record in self):
            raise UserError(_('El estado histórico se conserva como referencia de solo lectura.'))
        return super().write(values)
