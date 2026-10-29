"""Retain only the validated bank aliases when their old bridge is upgraded."""
from odoo import models

from ..hooks import LEGACY_FIELDS, preserve_legacy_xmlids


class IrModelData(models.Model):
    _inherit = 'ir.model.data'

    def _process_end(self, modules):
        if set(modules or ()) & set(LEGACY_FIELDS):
            # A later bridge-only upgrade does not execute the core's hooks.
            # Revalidate actual core ownership, then use the native loader
            # marker; every existing XMLID row/flag remains unchanged.
            preserve_legacy_xmlids(self.env)
        return super()._process_end(modules)
