from odoo import api, models
from ..migration_helpers import register_legacy_aliases


class ProducerEstimate(models.Model):
    _inherit = 'step.export.estimate'

    @api.model
    def _register_legacy_aliases(self):
        register_legacy_aliases(self.env.cr)
