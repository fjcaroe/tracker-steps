"""Keep analytic attribution optional on balance-sheet accounts."""
from odoo import models


class AnalyticPlan(models.Model):
    _inherit = 'account.analytic.plan'

    def _get_applicability(self, **kwargs):
        applicability = super()._get_applicability(**kwargs)
        # Keep explicit UI/model requests and unavailable plans unchanged.
        # Account type is the native chart classification, never a code prefix.
        if applicability == 'mandatory' and 'applicability' not in kwargs and kwargs.get('account'):
            account = self.env['account.account'].browse(kwargs['account']).exists()
            if account.internal_group in ('asset', 'liability', 'equity'):
                return 'optional'
        return applicability
