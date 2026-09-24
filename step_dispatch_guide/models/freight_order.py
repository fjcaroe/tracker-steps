from odoo import _, fields, models


class FreightOrder(models.Model):
    _inherit = "x_orden_de_flete"

    dispatch_guide_ids = fields.One2many(
        "step.dispatch.guide", "freight_order_id", string="Guías de despacho",
    )
    dispatch_guide_count = fields.Integer(compute="_compute_dispatch_guide_count")

    def _compute_dispatch_guide_count(self):
        for order in self:
            order.dispatch_guide_count = len(order.dispatch_guide_ids)

    def action_create_dispatch_guide(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Nueva guía de despacho"),
            "res_model": "step.dispatch.guide", "view_mode": "form", "target": "current",
            "context": {
                "default_freight_order_id": self.id,
                "default_date": self.x_studio_fecha,
                "default_carrier_id": self.x_studio_transportista.id,
                "default_truck_plate": self.vehicle_id.license_plate,
                "default_origin_address": self.route_id.origin,
                "default_destination_address": self.route_id.destination,
                "default_transfer_reason": self.x_name,
            },
        }

    def action_view_dispatch_guides(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Guías de despacho"),
            "res_model": "step.dispatch.guide", "view_mode": "list,form",
            "domain": [("freight_order_id", "=", self.id)],
            "context": {"default_freight_order_id": self.id},
        }

