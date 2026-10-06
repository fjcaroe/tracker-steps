from odoo import _, fields, models
from odoo.exceptions import UserError


def _reason(env, code):
    return env["step.dispatch.transfer.reason"].search([("code", "=", code)], limit=1)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    dispatch_guide_ids = fields.One2many(
        "step.dispatch.guide", "picking_id", string="Guías de despacho",
    )
    dispatch_guide_count = fields.Integer(compute="_compute_dispatch_guide_count")

    def _compute_dispatch_guide_count(self):
        for picking in self:
            picking.dispatch_guide_count = len(picking.dispatch_guide_ids)

    def _dispatch_guide_line_vals(self):
        self.ensure_one()
        kg_category = self.env.ref("uom.product_uom_categ_kgm")
        lines = []
        for move in self.move_ids.filtered(lambda item: item.product_uom_qty > 0):
            lots = move.move_line_ids.lot_id
            sale_line = move.sale_line_id if "sale_line_id" in move._fields else False
            lines.append(fields.Command.create({
                "product_id": move.product_id.id,
                "description": move.description_picking or move.product_id.display_name,
                "product_uom_id": move.product_uom.id,
                "quantity": move.product_uom_qty,
                "quantity_kg": move.product_uom_qty if move.product_uom.category_id == kg_category else 0,
                "lot_id": lots.id if len(lots) == 1 else False,
                "price_unit": sale_line.price_unit if sale_line else 0.0,
                "tax_ids": [fields.Command.set(sale_line.tax_id.ids)] if sale_line else False,
            }))
        return lines

    def action_create_dispatch_guide(self):
        """Entregas (venta) y traslados internos; las recepciones no llevan guía propia."""
        self.ensure_one()
        if self.picking_type_code not in ("outgoing", "internal"):
            raise UserError(_("La guía se crea desde una entrega o un traslado interno."))
        is_sale = self.picking_type_code == "outgoing" and bool(
            "sale_id" in self._fields and self.sale_id)
        reason = _reason(self.env, "1" if is_sale else "5")
        partner = self.partner_id or self.company_id.partner_id
        return {
            "type": "ir.actions.act_window",
            "name": _("Nueva guía de despacho"),
            "res_model": "step.dispatch.guide",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_picking_id": self.id,
                "default_partner_id": partner.id,
                "default_transfer_reason_id": reason.id,
                "default_origin_address": self.location_id.complete_name,
                "default_destination_address": (
                    partner.contact_address.replace("\n", ", ").strip(", ")
                    if self.picking_type_code == "outgoing" else self.location_dest_id.complete_name),
                "default_reference": self.origin or self.name,
                "default_line_ids": self._dispatch_guide_line_vals(),
            },
        }

    def action_view_dispatch_guides(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Guías de despacho"),
            "res_model": "step.dispatch.guide", "view_mode": "list,form",
            "domain": [("picking_id", "=", self.id)],
            "context": {"default_picking_id": self.id},
        }
