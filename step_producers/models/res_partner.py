"""Producer overview over the existing Steps records; no duplicate masters."""

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    step_producer_fundo_count = fields.Integer(compute="_compute_step_producer_counts")
    step_producer_estimate_count = fields.Integer(compute="_compute_step_producer_counts")
    step_producer_rate_count = fields.Integer(compute="_compute_step_producer_counts")
    step_producer_settlement_count = fields.Integer(compute="_compute_step_producer_counts")

    def _compute_step_producer_counts(self):
        for partner in self:
            partner.step_producer_fundo_count = self.env["step.fundo"].search_count([
                ("partner_id", "=", partner.id)])
            partner.step_producer_estimate_count = self.env["step.export.estimate"].search_count([
                ("producer_id", "=", partner.id)])
            partner.step_producer_rate_count = self.env["step.export.grower.rate"].search_count([
                ("producer_id", "=", partner.id)])
            partner.step_producer_settlement_count = self.env["step.export.producer.settlement"].search_count([
                ("producer_id", "=", partner.id)])

    def _step_producer_open(self, name, model, field):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": model,
            "view_mode": "list,form",
            "domain": [(field, "=", self.id)],
            "context": {"default_%s" % field: self.id},
        }

    def action_step_producer_fundos(self):
        return self._step_producer_open("Fundos", "step.fundo", "partner_id")

    def action_step_producer_estimates(self):
        return self._step_producer_open("Estimaciones", "step.export.estimate", "producer_id")

    def action_step_producer_rates(self):
        return self._step_producer_open("Tarifas", "step.export.grower.rate", "producer_id")

    def action_step_producer_settlements(self):
        return self._step_producer_open("Liquidaciones", "step.export.producer.settlement", "producer_id")
