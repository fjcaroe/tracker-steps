"""Preserve the original API flags during later report-bridge upgrades."""
from odoo import models

from ..hooks import LEGACY, preserve_legacy_xmlids


class IrModelData(models.Model):
    _inherit = 'ir.model.data'

    def _process_end(self, modules):
        if LEGACY in (modules or ()):
            # Mark only the exact aliases after validating actual ownership.
            # Other identifiers remain subject to the native cleanup policy.
            preserve_legacy_xmlids(self.env)
        return super()._process_end(modules)
