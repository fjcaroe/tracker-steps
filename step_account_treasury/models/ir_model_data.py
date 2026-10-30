"""Keep only verified, independently owned Treasury menu aliases loaded."""
from odoo import models

from ..report_ownership import NAMESPACES, preserve_menus


class IrModelData(models.Model):
    _inherit = 'ir.model.data'

    def _process_end(self, modules):
        if set(modules or ()) & set(NAMESPACES):
            # Only the five exact names, models, existing records and matching
            # owners are admitted. All other IDs retain native cleanup behavior.
            preserve_menus(self.env)
        return super()._process_end(modules)
