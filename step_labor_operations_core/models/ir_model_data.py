from odoo import models

from ..hooks import CORE, LEGACY, _owned


class ExternalIdentifiers(models.Model):
    _inherit = 'ir.model.data'

    def _step_retained_aliases(self):
        names = self._step_transferred_names(LEGACY, CORE, _owned)
        return [*super()._step_retained_aliases(), (LEGACY, CORE, names)]
