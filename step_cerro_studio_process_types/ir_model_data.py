from odoo import models


class ProcessViewIdentifiers(models.Model):
    _inherit = 'ir.model.data'

    def _step_retained_aliases(self):
        return [*super()._step_retained_aliases(),
                ('step_cerro_studio_packing', 'step_cerro_studio_process_types', ('process_types',))]
