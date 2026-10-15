"""Preserve an unambiguous entry attribution on its generated FX adjustment."""
import json
from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _sync_operational_adjustment(self):
        result = super()._sync_operational_adjustment()
        ordinary = self.line_ids.filtered(lambda line: not line.is_operational_exchange_adjustment)
        distributions = {
            json.dumps(line.analytic_distribution, sort_keys=True)
            for line in ordinary if line.analytic_distribution
        }
        if len(distributions) == 1:
            # Copy only an existing, unanimous attribution. Native validation
            # still rejects incomplete allocations and ambiguous empty ones.
            self.line_ids.filtered(lambda line: line.is_operational_exchange_adjustment
                                   and not line.analytic_distribution).write({
                'analytic_distribution': json.loads(distributions.pop()),
            })
        return result
