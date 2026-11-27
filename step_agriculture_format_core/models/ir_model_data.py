from odoo import models

from ..ownership import CORE, LEGACY, RECORDS


class FormatIdentifiers(models.Model):
    _inherit = 'ir.model.data'

    def _step_retained_aliases(self):
        names = (*RECORDS, 'model_stock_package_type')
        return [*super()._step_retained_aliases(), *((legacy, CORE, names) for legacy in LEGACY)]
