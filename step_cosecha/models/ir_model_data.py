from odoo import models

from ..hooks import FIELD_XMLID


class HarvestIdentifiers(models.Model):
    _inherit = 'ir.model.data'

    def _step_retained_aliases(self):
        names = ('model_stock_picking', FIELD_XMLID)
        return [*super()._step_retained_aliases(), ('step_hr', 'step_cosecha', names)]
