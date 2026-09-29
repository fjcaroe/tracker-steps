"""Datos de pesaje y tarjas en la recepción nativa de Inventario."""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare


class StockPicking(models.Model):
    _inherit = "stock.picking"

    step_fruit_reception_kind = fields.Selection([
        ("process", "Fruta a proceso"), ("packed", "Fruta embalada"),
    ], string="Tipo de recepción de fruta", index=True)
    step_fruit_weighing_method = fields.Selection([
        ("manual", "Manual"), ("scale", "Balanza"),
    ], string="Registro de pesaje", default="manual")
    step_fruit_weighing_by = fields.Selection([
        ("truck", "Por camión"), ("unit", "Por unidad de traslado"),
    ], string="Tipo de pesaje", default="truck")
    step_fruit_guide_date = fields.Date(string="Fecha guía productor")
    step_fruit_driver_id = fields.Many2one("res.partner", string="Chofer")
    step_fruit_driver_vat = fields.Char(related="step_fruit_driver_id.vat", string="RUT chofer")
    step_fruit_cost_center = fields.Char(string="Centro de costo / cuartel")
    step_fruit_gross_kg = fields.Float(string="Peso bruto kg", digits="Stock Weight")
    step_fruit_truck_tare_kg = fields.Float(string="Destare camión kg", digits="Stock Weight")
    step_fruit_container_tare_kg = fields.Float(string="Destare envases kg", digits="Stock Weight")
    step_fruit_transfer_tare_kg = fields.Float(string="Destare unidades traslado kg", digits="Stock Weight")
    step_fruit_net_kg = fields.Float(
        string="Peso neto fruta kg", compute="_compute_step_fruit_net_kg", digits="Stock Weight")

    @api.depends("step_fruit_gross_kg", "step_fruit_truck_tare_kg",
                 "step_fruit_container_tare_kg", "step_fruit_transfer_tare_kg")
    def _compute_step_fruit_net_kg(self):
        for picking in self:
            picking.step_fruit_net_kg = max(0.0, picking.step_fruit_gross_kg -
                picking.step_fruit_truck_tare_kg - picking.step_fruit_container_tare_kg -
                picking.step_fruit_transfer_tare_kg)

    @api.constrains("step_fruit_reception_kind", "picking_type_id")
    def _check_step_fruit_kind(self):
        for picking in self:
            if picking.step_fruit_reception_kind and picking.picking_type_code != "incoming":
                raise ValidationError(_("Las recepciones de fruta deben ser operaciones de entrada."))
            if picking.step_fruit_reception_kind and not picking.company_id.step_fruit_inventory_enabled:
                raise ValidationError(_("Habilite las recepciones agrícolas en la configuración de Inventario."))

    def _check_step_fruit_reception(self):
        for picking in self.filtered("step_fruit_reception_kind"):
            if not picking.fruit_fundo_id or not picking.fruit_species_id:
                raise ValidationError(_("Indique fundo y especie en la recepción de fruta."))
            if not picking.fruit_tag_line_ids:
                raise ValidationError(_("Registre las tarjas recibidas."))
            if picking.step_fruit_weighing_by == "truck":
                if picking.step_fruit_gross_kg <= 0:
                    raise ValidationError(_("Ingrese el peso bruto del camión."))
                if picking.step_fruit_net_kg <= 0:
                    raise ValidationError(_("El peso neto debe ser mayor a cero."))
                kilos = sum(picking.fruit_tag_line_ids.mapped("kilos"))
                if float_compare(kilos, picking.step_fruit_net_kg, precision_digits=2):
                    raise ValidationError(_("Los kilos de las tarjas no coinciden con el peso neto de la recepción."))
            for line in picking.fruit_tag_line_ids:
                if not line.package_id or line.package_id.name != line.tag_number:
                    raise ValidationError(_("Cada línea debe referir un paquete de stock con el mismo número de tarja."))
                expected = "C" if picking.step_fruit_reception_kind == "process" else "E"
                if line.package_id.step_tag_kind != expected:
                    raise ValidationError(_("El tipo de tarja no coincide con el tipo de recepción."))
                if line.package_id not in picking.move_line_ids.mapped("result_package_id"):
                    raise ValidationError(_("Asigne cada tarja al paquete resultante en las operaciones de stock."))

    def button_validate(self):
        self._check_step_fruit_reception()
        result = super().button_validate()
        for picking in self.filtered(lambda record: record.step_fruit_reception_kind and record.state == "done"):
            producer = picking.fruit_fundo_id.partner_id
            if not producer:
                raise ValidationError(_("El fundo de la recepción debe tener un productor."))
            for line in picking.fruit_tag_line_ids:
                package = line.package_id
                if package.step_tag_state == "created":
                    package.write({
                        "fundo_id": picking.fruit_fundo_id.id,
                        "step_export_season_id": picking.fruit_season_id.id,
                        "especie_id": picking.fruit_species_id.id,
                        "variedad_id": picking.fruit_variety_id.id,
                    })
                if not package.step_tag_line_ids:
                    products = package.quant_ids.mapped("product_id")
                    product = line.product_id or (products if len(products) == 1 else False)
                    quants = package.quant_ids.filtered(lambda quant: quant.product_id == product)
                    quantity = sum(quants.mapped("quantity"))
                    if not product or quantity <= 0:
                        raise ValidationError(_("La tarja debe contener un único producto en stock o indicarlo en el detalle."))
                    package.write({
                        "step_producer_id": producer.id,
                        "box_count": line.box_count,
                        "step_tag_line_ids": [(0, 0, {
                            "producer_id": producer.id,
                            "product_id": product.id,
                            "quantity": quantity,
                            "kilos": line.kilos,
                            "boxes": line.box_count,
                        })],
                    })
                if package.step_tag_state == "created":
                    package.action_step_validate_tag()
        return result

    def action_step_import_fruit_tags(self):
        self.ensure_one()
        if not self.step_fruit_reception_kind or self.state == "done":
            raise ValidationError(_("Seleccione una recepción de fruta sin validar."))
        return {
            "type": "ir.actions.act_window", "name": _("Importar tarjas desde Excel"),
            "res_model": "step.fruit.reception.import", "view_mode": "form",
            "target": "new", "context": {"default_picking_id": self.id},
        }


class StepPackingPickingTagLine(models.Model):
    _inherit = "step.packing.picking.tag.line"

    package_id = fields.Many2one("stock.quant.package", string="Paquete de stock")
    product_id = fields.Many2one("product.product", string="Producto")
    gross_kg = fields.Float(string="Peso bruto kg", digits="Stock Weight")
    tare_kg = fields.Float(string="Destare kg", digits="Stock Weight")
    net_kg = fields.Float(string="Peso neto kg", compute="_compute_step_net_kg", digits="Stock Weight")
    box_count = fields.Float(string="Cajas", digits="Product Unit of Measure")

    @api.depends("gross_kg", "tare_kg")
    def _compute_step_net_kg(self):
        for line in self:
            line.net_kg = max(0.0, line.gross_kg - line.tare_kg)

    @api.constrains("gross_kg", "tare_kg", "kilos", "package_id")
    def _check_step_weighing(self):
        for line in self:
            if line.gross_kg or line.tare_kg:
                if line.gross_kg <= line.tare_kg:
                    raise ValidationError(_("El peso bruto de la tarja debe superar el destare."))
                if float_compare(line.kilos, line.net_kg, precision_digits=2):
                    raise ValidationError(_("Los kilos de la tarja no coinciden con su pesaje."))
