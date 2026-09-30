"""Reserva operativa de tarjas para un instructivo de Packing."""

from collections import defaultdict

from odoo import fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class PackingStockReservation(models.Model):
    _inherit = "step.export.stock.reservation"

    step_packing_order_id = fields.Many2one("step.packing.order", string="Orden de proceso")
    step_package_ids = fields.Many2many("stock.quant.package", relation="step_packing_reserved_package_rel",
        string="Tarjas reservadas")
    step_reservation_state = fields.Selection([
        ("draft", "Creada"), ("reserved", "Reservada"), ("released", "Liberada"),
    ], default="draft", string="Estado Packing", copy=False)
    step_picking_id = fields.Many2one("stock.picking", string="Reserva en Inventario", readonly=True, copy=False)

    def action_step_reserve(self):
        for reservation in self:
            if reservation.step_reservation_state != "draft" or not reservation.step_packing_order_id:
                raise UserError(_("Seleccione una orden de Packing en una reserva creada."))
            if reservation.step_packing_order_id.state != "validated" or not reservation.step_package_ids:
                raise ValidationError(_("La orden debe estar validada y tener tarjas para reservar."))
            if reservation.step_packing_order_id.company_id != reservation.company_id:
                raise ValidationError(_("La reserva y la orden pertenecen a distintas empresas."))
            packages = reservation.step_package_ids
            if any(not tag.is_fruit_tag or tag.step_tag_state != "validated" for tag in packages):
                raise ValidationError(_("Solo se reservan tarjas de fruta validadas."))
            if packages & reservation.step_packing_order_id.production_ids.mapped("step_packing_input_tag_ids"):
                raise ValidationError(_("Libere primero la reserva antes de asignar tarjas a una OT."))
            quants = packages.mapped("quant_ids").filtered(lambda quant: quant.quantity > 0)
            locations = quants.mapped("location_id")
            if len(locations) != 1 or locations.usage != "internal":
                raise ValidationError(_("Las tarjas deben tener existencias en una ubicación interna común."))
            if any(not package.quant_ids.filtered(lambda quant: quant.quantity > 0) for package in packages):
                raise ValidationError(_("Una tarja no contiene stock disponible."))
            groups = defaultdict(float)
            for quant in quants:
                groups[quant.product_id] += quant.quantity
                available = self.env["stock.quant"]._get_available_quantity(
                    quant.product_id, locations, lot_id=quant.lot_id,
                    package_id=quant.package_id, owner_id=quant.owner_id, strict=True)
                if float_compare(available, quant.quantity, precision_rounding=quant.product_id.uom_id.rounding) < 0:
                    raise ValidationError(_("La tarja %s ya tiene stock reservado.") % quant.package_id.name)
            warehouse = self.env["stock.warehouse"].search([
                ("company_id", "=", reservation.company_id.id)], limit=1)
            if not warehouse:
                raise ValidationError(_("Configure una bodega para reservar fruta."))
            picking = self.env["stock.picking"].create({
                "picking_type_id": warehouse.int_type_id.id,
                "company_id": reservation.company_id.id,
                "origin": reservation.name,
                "location_id": locations.id,
                "location_dest_id": locations.id,
                "move_ids": [(0, 0, {
                    "name": product.display_name, "product_id": product.id,
                    "product_uom_qty": quantity, "product_uom": product.uom_id.id,
                    "location_id": locations.id, "location_dest_id": locations.id,
                }) for product, quantity in groups.items()],
            })
            picking.action_confirm()
            # Some picking types reserve automatically at confirmation. Drop
            # that generic allocation, then reserve the requested packages.
            picking.do_unreserve()
            for quant in quants:
                move = picking.move_ids.filtered(lambda row: row.product_id == quant.product_id)
                reserved = move._update_reserved_quantity(
                    quant.quantity, locations, lot_id=quant.lot_id,
                    package_id=quant.package_id, owner_id=quant.owner_id, strict=True)
                if float_compare(reserved, quant.quantity, precision_rounding=quant.product_id.uom_id.rounding):
                    raise ValidationError(_("No se pudo reservar toda la tarja %s.") % quant.package_id.name)
            reservation.write({"step_picking_id": picking.id, "step_reservation_state": "reserved"})
        return True

    def action_step_release(self):
        for reservation in self:
            if reservation.step_reservation_state != "reserved" or not reservation.step_picking_id:
                raise UserError(_("La reserva no está activa."))
            reservation.step_picking_id.action_cancel()
            reservation.step_reservation_state = "released"
        return True

    def write(self, vals):
        locked = {"step_packing_order_id", "step_package_ids", "company_id", "step_picking_id"}
        if locked.intersection(vals) and any(record.step_reservation_state != "draft" for record in self):
            raise UserError(_("Una reserva utilizada no se modifica."))
        return super().write(vals)
