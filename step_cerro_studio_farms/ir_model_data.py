from odoo import models


class FarmViewIdentifiers(models.Model):
    _inherit = 'ir.model.data'

    def _step_retained_aliases(self):
        return [*super()._step_retained_aliases(),
                ('step_cerro_studio_agriculture', 'step_cerro_studio_farms', ('farms',))]
