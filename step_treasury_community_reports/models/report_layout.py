from odoo import models


class TreasuryReportLayout(models.Model):
    _inherit = 'ir.actions.report'

    def _get_layout(self):
        # The native PDF pipeline wraps bodies, headers and footers in this
        # layout. Scope the asset-free layout to our report; all other reports
        # keep the standard implementation and their existing assets.
        if len(self) == 1 and self.report_name == 'step_treasury_community_reports.print_document':
            return self.env.ref('step_treasury_community_reports.minimal_layout')
        return super()._get_layout()
