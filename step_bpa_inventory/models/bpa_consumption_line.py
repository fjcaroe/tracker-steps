from odoo import api, fields, models


class BpaInventoryConsumptionLine(models.Model):
    _name = "step.bpa.inventory.consumption.line"
    _description = "Consumo de productos de una Aplicación foliar BPA (para Inventario)"

    application_id = fields.Many2one(
        "x_aplicacion_foliar", string="Aplicación foliar",
        required=True, ondelete="cascade", index=True,
    )
    product_id = fields.Many2one("product.product", string="Producto", required=True)
    product_uom_id = fields.Many2one(
        "uom.uom", string="UdM", compute="_compute_product_uom_id",
        store=True, readonly=False, precompute=True,
    )
    product_qty = fields.Float(string="Cantidad", required=True, default=1.0)
    inventory_move_id = fields.Many2one(
        "stock.move", string="Movimiento de Inventario", readonly=True, copy=False,
    )

    @api.depends("product_id")
    def _compute_product_uom_id(self):
        for line in self:
            line.product_uom_id = line.product_id.uom_id
