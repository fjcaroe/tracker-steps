from odoo import models
from odoo.addons.step_l10n_cl_caf_custody_core.custody import CAFCustodyMixin, MODEL


class NativeCAFCustody(CAFCustodyMixin, models.Model):
    _inherit = MODEL
    # No field declarations, original-method overrides, defaults or XML data.
