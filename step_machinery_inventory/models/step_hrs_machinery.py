from odoo import Command, _, fields, models
from odoo.exceptions import UserError

#: Referencia externa del tipo de operación de consumo de combustible,
#: definido en ``data/stock_data.xml``.
CONSUMPTION_PICKING_TYPE_XMLID = "step_machinery_inventory.picking_type_machinery_consumption"


class StepHrsMachinery(models.Model):
    _inherit = "step.hrs.machinery"

    inventory_picking_id = fields.Many2one(
        "stock.picking", string="Movimiento de Inventario",
        readonly=True, copy=False,
        help="Salida de combustible generada desde esta OT. Se crea una sola "
             "vez: volver a pulsar el botón reabre el mismo movimiento en "
             "vez de duplicarlo.",
    )

    def action_generate_inventory_move(self):
        self.ensure_one()
        if self.state not in ("costed", "accounted"):
            raise UserError(_("Sólo se puede generar el movimiento de Inventario para una OT Costeada."))
        if self.inventory_picking_id:
            return self._open_inventory_picking()

        lines = self.hrs_machinery_line.filtered(
            lambda line: line.lrts_combustible > 0 and line.machinery_ids.step_product_id
        )
        if not lines:
            raise UserError(_(
                "No hay líneas con litros de combustible y producto de combustible "
                "configurado en la maquinaria (pestaña Costo hora, sección Combustibles)."
            ))

        picking_type = self.env.ref(CONSUMPTION_PICKING_TYPE_XMLID)
        move_vals = []
        for line in lines:
            product = line.machinery_ids.step_product_id.product_variant_id
            if not product:
                raise UserError(_(
                    "El producto de combustible de %s no tiene una variante utilizable."
                ) % line.machinery_ids.display_name)
            move_vals.append(Command.create({
                "name": product.display_name,
                "product_id": product.id,
                "product_uom_qty": line.lrts_combustible,
                "product_uom": product.uom_id.id,
                "location_id": picking_type.default_location_src_id.id,
                "location_dest_id": picking_type.default_location_dest_id.id,
                "step_hrs_machinery_line_id": line.id,
                "company_id": self.company_id.id,
            }))

        picking = self.env["stock.picking"].create({
            "picking_type_id": picking_type.id,
            "location_id": picking_type.default_location_src_id.id,
            "location_dest_id": picking_type.default_location_dest_id.id,
            "origin": self.name or self.ot_number,
            "company_id": self.company_id.id,
            "move_ids": move_vals,
        })
        picking.action_confirm()
        self.inventory_picking_id = picking.id
        return self._open_inventory_picking()

    def _open_inventory_picking(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "res_id": self.inventory_picking_id.id,
            "view_mode": "form",
            "target": "current",
        }
