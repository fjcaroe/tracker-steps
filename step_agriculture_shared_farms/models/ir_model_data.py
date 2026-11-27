from odoo import models

from ..hooks import CURRENT, IDENTITIES, LEGACY


class ExternalIdentifiers(models.Model):
    _inherit = 'ir.model.data'

    def _step_retained_aliases(self):
        return [*super()._step_retained_aliases(), (LEGACY, CURRENT, tuple(IDENTITIES))]
