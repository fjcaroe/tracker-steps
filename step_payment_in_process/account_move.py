from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _get_invoice_in_payment_state(self):
        """Keep a registered payment pending until its payment or journal workflow confirms settlement."""
        return "in_payment"
