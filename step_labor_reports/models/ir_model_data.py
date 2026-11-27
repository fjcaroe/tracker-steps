from odoo import models

from ..hooks import owned
from ..ownership import CORE, LEGACY


class ReportIdentifiers(models.Model):
    _inherit = 'ir.model.data'

    def _step_retained_aliases(self):
        pairs = super()._step_retained_aliases()
        for legacy in LEGACY:
            names = self._step_transferred_names(legacy, CORE, lambda row: owned(self.env, row))
            pairs = [*pairs, (legacy, CORE, names)]
        return pairs
