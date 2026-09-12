from odoo import Command, _, fields, models
from odoo.exceptions import UserError

#: Estados de ``x_aplicacion_foliar`` a partir de los cuales ya existe un
#: costeo que puede convertirse en movimiento de Inventario.
COSTEABLE_STATES = ("status3", "Contabilizado")

#: Referencia externa del tipo de operación de consumo BPA, definido en
#: ``data/stock_data.xml``.
CONSUMPTION_PICKING_TYPE_XMLID = "step_bpa_inventory.picking_type_bpa_consumption"


class BpaFoliarApplicationInventory(models.Model):
    _inherit = "x_aplicacion_foliar"

    consumption_line_ids = fields.One2many(
        "step.bpa.inventory.consumption.line", "application_id",
        string="Consumo de productos",
    )
    inventory_picking_id = fields.Many2one(
        "stock.picking", string="Movimiento de Inventario",
        readonly=True, copy=False,
        help="Salida de productos desde Bodega BPA generada desde esta "
             "OT-BPA. Se crea una sola vez: volver a pulsar el botón reabre "
             "el mismo movimiento en vez de duplicarlo.",
    )

    def action_generate_inventory_move(self):
        self.ensure_one()
        if self.state not in COSTEABLE_STATES:
            raise UserError(_("Sólo se puede generar el movimiento de Inventario para una OT-BPA Costeada."))
        if self.inventory_picking_id:
            return self._open_inventory_picking()
        if not self.consumption_line_ids:
            raise UserError(_(
                "Agregue al menos una línea en \"Consumo de productos\" antes de "
                "generar el movimiento de Inventario."
            ))

        picking_type = self.env.ref(CONSUMPTION_PICKING_TYPE_XMLID)
        move_vals = []
        for line in self.consumption_line_ids:
            move_vals.append(Command.create({
                "name": line.product_id.display_name,
                "product_id": line.product_id.id,
                "product_uom_qty": line.product_qty,
                "product_uom": line.product_uom_id.id or line.product_id.uom_id.id,
                "location_id": picking_type.default_location_src_id.id,
                "location_dest_id": picking_type.default_location_dest_id.id,
                "company_id": self.company_id.id,
            }))

        picking = self.env["stock.picking"].create({
            "picking_type_id": picking_type.id,
            "location_id": picking_type.default_location_src_id.id,
            "location_dest_id": picking_type.default_location_dest_id.id,
            "origin": self.x_studio_nmero_ot_bpa or self.x_name,
            "company_id": self.company_id.id,
            "move_ids": move_vals,
        })
        picking.action_confirm()
        for line, move in zip(self.consumption_line_ids, picking.move_ids):
            line.inventory_move_id = move.id
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
