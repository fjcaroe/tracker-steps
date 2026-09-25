from odoo import api, fields, models


class StockMove(models.Model):
    """El documento de diseño pide agregar Kilos a la línea de detalle de la
    tarja. Se calcula sobre stock.move (demanda) en vez de sobre
    stock.move.line: es un campo estable entre versiones de Odoo
    (product_uom_qty existe desde hace muchas versiones), mientras que el
    nombre del campo de cantidad hecha en stock.move.line cambió entre
    versiones (qty_done -> quantity + picked)."""

    _inherit = "stock.move"

    fruit_tag_kilos = fields.Float(
        string="Kilos",
        compute="_compute_fruit_tag_kilos",
        digits="Stock Weight",
        help="Cantidad convertida a kilogramos usando el peso del producto.",
    )

    @api.depends("product_uom_qty", "product_uom", "product_id.weight", "product_id.uom_id")
    def _compute_fruit_tag_kilos(self):
        for move in self:
            kg = self.env.ref("uom.product_uom_kgm")
            if move.product_uom.category_id == kg.category_id:
                move.fruit_tag_kilos = move.product_uom._compute_quantity(move.product_uom_qty, kg, round=False)
            else:
                units = move.product_uom._compute_quantity(move.product_uom_qty, move.product_id.uom_id, round=False)
                move.fruit_tag_kilos = units * move.product_id.weight
