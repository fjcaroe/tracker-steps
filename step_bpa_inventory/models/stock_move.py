from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    step_bpa_analytic_distribution = fields.Json(string="Distribución analítica BPA", readonly=True)

    def _generate_valuation_lines_data(self, partner_id, qty, debit_value, credit_value,
                                       debit_account_id, credit_account_id, svl_id, description):
        values = super()._generate_valuation_lines_data(
            partner_id, qty, debit_value, credit_value, debit_account_id, credit_account_id, svl_id, description,
        )
        if (self.picking_type_id.sequence_code == "BPACONS" and self.location_dest_id.usage == "production"
                and self.step_bpa_analytic_distribution and not values["debit_line_vals"].get("analytic_distribution")):
            values["debit_line_vals"]["analytic_distribution"] = self.step_bpa_analytic_distribution
        return values
