from odoo import Command, _, fields, models
from odoo.exceptions import UserError

#: Estados de ``step.agriculture.application`` a partir de los cuales ya existe un
#: costeo que puede convertirse en movimiento de Inventario.
COSTEABLE_STATES = ("status3", "Contabilizado")


class BpaFoliarApplicationInventory(models.Model):
    _inherit = "step.agriculture.application"

    consumption_line_ids = fields.One2many(
        "step.bpa.inventory.consumption.line", "application_id",
        string="Consumo de productos",
    )
    inventory_picking_id = fields.Many2one(
        "stock.picking", string="Movimiento de Inventario",
        readonly=True, copy=False, check_company=True,
        help="Salida de productos desde Bodega BPA generada desde esta "
             "OT-BPA. Se crea una sola vez: volver a pulsar el botón reabre "
             "el mismo movimiento en vez de duplicarlo.",
    )

    def action_generate_inventory_move(self):
        self.ensure_one()
        self.check_access("write")
        if self.state not in COSTEABLE_STATES:
            raise UserError(_("Sólo se puede generar el movimiento de Inventario para una OT-BPA Costeada."))
        if self.inventory_picking_id:
            return self._open_inventory_picking()
        if not self.consumption_line_ids:
            raise UserError(_(
                "Agregue al menos una línea en \"Consumo de productos\" antes de "
                "generar el movimiento de Inventario."
            ))

        picking_type = self.env["stock.picking.type"].search([
            ("company_id", "=", self.company_id.id),
            ("code", "=", "internal"),
            ("sequence_code", "=", "BPACONS"),
        ], limit=2)
        if len(picking_type) != 1 or not picking_type.default_location_src_id or not picking_type.default_location_dest_id:
            raise UserError(_("Inventario debe configurar un único tipo de operación Consumo BPA para %s.", self.company_id.display_name))
        locations = picking_type.default_location_src_id | picking_type.default_location_dest_id
        if (locations.company_id - self.company_id or picking_type.default_location_src_id.usage != "internal"
                or picking_type.default_location_dest_id.usage != "production"):
            raise UserError(_("Consumo BPA requiere una ubicación interna y otra de producción de la empresa de la aplicación."))
        analytic_distribution = self._bpa_cost_distribution_by_hectare()
        move_vals = []
        for line in self.consumption_line_ids:
            vals = {
                "name": line.product_id.display_name,
                "product_id": line.product_id.id,
                "product_uom_qty": line.product_qty,
                "product_uom": line.product_uom_id.id or line.product_id.uom_id.id,
                "location_id": picking_type.default_location_src_id.id,
                "location_dest_id": picking_type.default_location_dest_id.id,
                "company_id": self.company_id.id,
            }
            if analytic_distribution:
                vals["step_bpa_analytic_distribution"] = analytic_distribution
                if "analytic_distribution" in self.env["stock.move"]._fields:
                    vals["analytic_distribution"] = analytic_distribution
            move_vals.append(Command.create(vals))

        picking = self.env["stock.picking"].create({
            "picking_type_id": picking_type.id,
            "location_id": picking_type.default_location_src_id.id,
            "location_dest_id": picking_type.default_location_dest_id.id,
            "origin": self.nmero_ot_bpa or self.name,
            "company_id": self.company_id.id,
            "move_ids": move_vals,
        })
        picking.action_confirm()
        for line, move in zip(self.consumption_line_ids, picking.move_ids):
            line.inventory_move_id = move.id
        self.inventory_picking_id = picking.id
        return self._open_inventory_picking()

    def _bpa_cost_distribution_by_hectare(self):
        """Distribuye el costo entre centros de costo según sus hectáreas aplicadas."""
        self.ensure_one()
        hectares_by_account = {}
        for line in self.machinery_ids:
            account = line.cost_center_id
            hectares = line.has_aplicadas
            if not account or not hectares:
                continue
            hectares_by_account[account.id] = hectares_by_account.get(account.id, 0.0) + hectares
        total_hectares = sum(hectares_by_account.values())
        if not total_hectares:
            return False
        return {
            str(account_id): hectares * 100.0 / total_hectares
            for account_id, hectares in hectares_by_account.items()
        }

    def _open_inventory_picking(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "res_id": self.inventory_picking_id.id,
            "view_mode": "form",
            "target": "current",
        }
