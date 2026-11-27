from odoo import fields, models

from .hooks import OWNER, ORIGINAL, NAMES


class Partner(models.Model):
    _inherit = 'res.partner'

    step_export_fundo_ids = fields.One2many('step.fundo', 'partner_id', string='Fundos')


class FarmDirectoryIdentifiers(models.Model):
    _inherit = 'ir.model.data'

    def _step_retained_aliases(self):
        return [*super()._step_retained_aliases(), (ORIGINAL, OWNER, NAMES),
                ('step_export', OWNER, ('field_res_partner__step_export_fundo_ids',))]
