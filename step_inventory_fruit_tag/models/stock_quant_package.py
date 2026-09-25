from odoo import api, fields, models


class StockQuantPackage(models.Model):
    """Adapta el paquete nativo de Inventario a la "tarja de fruta de
    exportación" pedida en el ticket 22, en vez de crear un modelo nuevo:
    el propio documento de diseño del cliente dice "Adaptar el concepto de
    empaquetado de inventario a la tarja de fruta" y marca "Referencia: es
    el número de la tarja o pallets (ok)" -- es decir, reutilizar
    stock.quant.package.name, no reinventar la numeración."""

    _inherit = "stock.quant.package"

    is_fruit_tag = fields.Boolean(
        string="Es tarja de fruta",
        help="Habilita los campos de clasificación de fruta y el reporte de "
             "tarja de exportación para este paquete.",
    )
    fundo_id = fields.Many2one(
        "step.fundo", string="Fundo",
        help="Al elegir un Fundo se propone su Productor como Propietario "
             "del paquete (campo nativo owner_id); puede sobrescribirse.",
    )
    especie_id = fields.Many2one("step.especie", string="Especie")
    variedad_id = fields.Many2one(
        "step.variedad", string="Variedad",
        domain="[('especie_id', '=', especie_id)]",
    )
    fruit_type = fields.Selection(
        selection=[("conventional", "Convencional"), ("organic", "Orgánico")],
        string="Tipo fruta",
    )
    fruit_category_id = fields.Many2one(
        "step.management.fruit.category", string="Categoría")
    fruit_class_id = fields.Many2one(
        "step.management.fruit.class", string="Clase de fruta")
    fruit_caliber_id = fields.Many2one(
        "step.management.fruit.caliber", string="Calibre")
    fruit_quality_id = fields.Many2one(
        "step.management.fruit.quality", string="Calidad")
    label = fields.Char(string="Etiqueta", help="Marca o cliente.")
    certificate = fields.Char(string="Certificado")
    ot_proceso = fields.Char(string="OT Proceso")
    process_type = fields.Char(string="Tipo proceso")
    process_line = fields.Integer(string="Línea")
    op_folio = fields.Char(string="Folio OP")
    packing_plant = fields.Char(string="Packing")
    box_count = fields.Integer(string="Cantidad cajas")
    kilos_total = fields.Float(
        string="Kilos", compute="_compute_kilos_total", store=True,
        digits="Stock Weight",
        help="Suma de cantidad × peso del producto (kg) de cada quant contenido.",
    )

    @api.depends("quant_ids.quantity", "quant_ids.product_id.weight", "quant_ids.product_id.uom_id")
    def _compute_kilos_total(self):
        for package in self:
            package.kilos_total = sum(
                (quant.product_id.uom_id._compute_quantity(quant.quantity, self.env.ref("uom.product_uom_kgm"), round=False)
                 if quant.product_id.uom_id.category_id == self.env.ref("uom.product_uom_kgm").category_id
                 else quant.quantity * quant.product_id.weight)
                for quant in package.quant_ids
            )

    @api.onchange("fundo_id")
    def _onchange_fundo_id(self):
        for package in self:
            if package.fundo_id.partner_id:
                package.owner_id = package.fundo_id.partner_id
