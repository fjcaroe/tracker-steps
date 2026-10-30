"""Use official Float's unlimited NUMERIC storage, retaining the normal Float API.

digits=False selects NUMERIC in the pinned official field implementation and
adds no decimal rounding. Reading through Float remains a binary Python API;
only the unchanged SQL NUMERIC is authoritative for original stored precision.
"""
from odoo import fields, models

from ..input_storage import admit_original_input_storage


class Input(models.Model):
    _inherit = "hr.payslip.input"

    amount = fields.Float(digits=False, required=False, default=None)

    def _auto_init(self):
        # Also protect an ordinary schema recheck that did not run an API
        # migration. Never let the ORM silently cast an existing Float8 column.
        admit_original_input_storage(self.env.cr)
        return super()._auto_init()
