"""Customer claims linked to shipments and fruit tags."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ExportClaim(models.Model):
    _inherit = "step.export.customer.claim"

    state = fields.Selection([
        ("entered", "Ingresado"), ("accepted", "Aceptado"),
        ("rejected", "Rechazado"),
    ], required=True, default="entered", tracking=True)
    receiver_id = fields.Many2one("res.partner", string="Recibidor", required=True)
    shipment_ids = fields.Many2many("step.export.export", string="Embarques")
    tag_ids = fields.Many2many("stock.quant.package", string="Tarjas")
    claim_date = fields.Date(default=fields.Date.context_today, required=True)
    description = fields.Html(string="Descripción")
    claimed_amount_usd = fields.Monetary(string="Monto reclamado USD", currency_field="usd_currency_id")
    accepted_amount_usd = fields.Monetary(string="Monto aceptado USD", currency_field="usd_currency_id")
    usd_currency_id = fields.Many2one("res.currency", default=lambda self: self.env.ref("base.USD"))

    def action_accept(self):
        for claim in self:
            if claim.state != "entered" or not claim.shipment_ids:
                raise UserError(_("El reclamo debe estar ingresado y tener embarques asociados."))
            if claim.accepted_amount_usd < 0 or claim.accepted_amount_usd > claim.claimed_amount_usd:
                raise UserError(_("El monto aceptado debe estar entre cero y el monto reclamado."))
            if claim.tag_ids - claim.shipment_ids.mapped("tag_ids"):
                raise UserError(_("Las tarjas reclamadas deben pertenecer a los embarques indicados."))
            if any(shipment.settlement_id for shipment in claim.shipment_ids):
                raise UserError(_("El embarque ya está liquidado; registre un ajuste posterior separado."))
            claim.shipment_ids.write({"claim_ids": [(4, claim.id)]})
            claim.tag_ids.write({"step_export_claim_ids": [(4, claim.id)]})
            claim.state = "accepted"
        return True

    def action_reject(self):
        if any(claim.state != "entered" for claim in self):
            raise UserError(_("Solo puede rechazar reclamos ingresados."))
        self.write({"state": "rejected"})
        return True

    def write(self, vals):
        locked = {"receiver_id", "shipment_ids", "tag_ids", "claimed_amount_usd",
                  "accepted_amount_usd", "claim_date"}
        if locked.intersection(vals) and any(claim.state != "entered" for claim in self):
            raise UserError(_("El reclamo resuelto conserva sus antecedentes."))
        return super().write(vals)
