from odoo import _, fields, models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    dispatch_guide_ids = fields.One2many(
        "step.dispatch.guide", "picking_id", string="Guías de despacho",
    )
    dispatch_guide_count = fields.Integer(compute="_compute_dispatch_guide_count")

    def _compute_dispatch_guide_count(self):
        for picking in self:
            picking.dispatch_guide_count = len(picking.dispatch_guide_ids)

    def action_create_dispatch_guide(self):
        self.ensure_one()
        if self.picking_type_code != "outgoing":
            raise UserError(_("La guía se crea desde una operación de salida."))
        lines = []
        for move in self.move_ids.filtered(lambda item: item.product_uom_qty > 0):
            lines.append((0, 0, {
                "product_id": move.product_id.id,
                "description": move.description_picking or move.product_id.display_name,
                "product_uom_id": move.product_uom.id,
                "quantity": move.product_uom_qty,
                "quantity_kg": move.product_uom_qty if move.product_uom.category_id == self.env.ref("uom.product_uom_categ_kgm") else 0,
            }))
        return {
            "type": "ir.actions.act_window",
            "name": _("Nueva guía de despacho"),
            "res_model": "step.dispatch.guide",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_picking_id": self.id,
                "default_partner_id": self.partner_id.id,
                "default_origin_address": self.location_id.complete_name,
                "default_destination_address": self.partner_id.contact_address or self.location_dest_id.complete_name,
                "default_transfer_reason": self.origin or self.name,
                "default_line_ids": lines,
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

