from odoo import _, fields, models
from odoo.exceptions import UserError


class FreightOrder(models.Model):
    _inherit = "step.freight.order"

    dispatch_guide_ids = fields.One2many(
        "step.dispatch.guide", "freight_order_id", string="Guías de despacho",
    )
    dispatch_guide_count = fields.Integer(compute="_compute_dispatch_guide_count")

    def _compute_dispatch_guide_count(self):
        for order in self:
            order.dispatch_guide_count = len(order.dispatch_guide_ids)

    def action_create_dispatch_guide(self):
        self.ensure_one()
        route = self.route_id or self.detail_ids.mapped("route_id")
        vehicles = self.vehicle_id or self.detail_ids.mapped("vehicle_id")
        drivers = self.detail_ids.mapped("driver_id")
        if len(route) != 1:
            raise UserError(_("Para crear una guía, el flete debe tener un único tramo. Separe los despachos con tramos distintos."))
        if len(vehicles) > 1 or len(drivers) > 1:
            raise UserError(_("Para crear una guía, las líneas deben usar el mismo camión y chofer. Separe los despachos distintos."))
        return {
            "type": "ir.actions.act_window", "name": _("Nueva guía de despacho"),
            "res_model": "step.dispatch.guide", "view_mode": "form", "target": "current",
            "context": {
                "default_freight_order_id": self.id,
                "default_freight_paid": True,
                "default_freight_route_id": route.id,
                "default_date": self.date,
                "default_carrier_id": self.freight_carrier_id.id,
                "default_vehicle_id": vehicles.id,
                "default_driver_partner_id": drivers.id,
                "default_origin_address": route.origin,
                "default_destination_address": route.destination,
                "default_reference": self.name,
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
