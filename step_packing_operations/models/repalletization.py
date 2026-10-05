"""Repaletizado con traslado nativo de stock entre paquetes de una ubicación."""

from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class PackingRepack(models.Model):
    _name = "step.packing.repack"
    _description = "Repaletizado de fruta"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _check_company_auto = True

    name = fields.Char(required=True, default="Nuevo", copy=False, readonly=True)
    state = fields.Selection([("draft", "Creado"), ("done", "Validado")], default="draft", tracking=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    line_ids = fields.One2many("step.packing.repack.line", "repack_id", string="Distribución de cajas")
    picking_id = fields.Many2one("stock.picking", string="Movimiento de Inventario", readonly=True, copy=False)
    boxes_total = fields.Float(compute="_compute_totals", string="Cajas", digits="Product Unit of Measure")
    kilos_total = fields.Float(compute="_compute_totals", string="Kilos", digits="Stock Weight")

    @api.depends("line_ids.boxes", "line_ids.kilos")
    def _compute_totals(self):
        for repack in self:
            repack.boxes_total = sum(repack.line_ids.mapped("boxes"))
            repack.kilos_total = sum(repack.line_ids.mapped("kilos"))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "Nuevo") == "Nuevo":
                vals["name"] = self.env["ir.sequence"].next_by_code("step.packing.repack") or "Nuevo"
        return super().create(vals_list)

    def write(self, vals):
        if any(repack.state == "done" for repack in self) and {"line_ids", "company_id", "picking_id"}.intersection(vals):
            raise UserError(_("Un repaletizado validado no se modifica."))
        return super().write(vals)

    def unlink(self):
        if any(repack.state == "done" for repack in self):
            raise UserError(_("Un repaletizado validado no se elimina."))
        return super().unlink()

    def _check_repack(self):
        self.ensure_one()
        if self.state != "draft" or not self.line_ids:
            raise UserError(_("Agregue líneas a un repaletizado creado."))
        sources = self.line_ids.mapped("source_package_id")
        targets = self.line_ids.mapped("target_package_id")
        if sources & targets:
            raise ValidationError(_("Una tarja no puede ser origen y destino del mismo repaletizado."))
        if len(set(sources.mapped("step_tag_kind"))) != 1 or len(set(targets.mapped("step_tag_kind"))) != 1:
            raise ValidationError(_("No mezcle tipos de tarja en un proceso."))
        if sources[0].step_tag_kind != targets[0].step_tag_kind:
            raise ValidationError(_("La tarja de destino debe conservar el tipo C, E o N."))
        attributes = ("step_tag_kind", "variedad_id", "fruit_quality_id", "fruit_category_id",
                      "fruit_caliber_id", "label", "package_type_id", "step_packing_result")
        reference = sources[0]
        for package in sources | targets:
            if not package.is_fruit_tag or any(package[field] != reference[field] for field in attributes):
                raise ValidationError(_("Variedad, calidad, categoría, calibre, etiqueta, embalaje y tipo deben conservarse."))
        if any(package.step_tag_state != "validated" for package in sources):
            raise ValidationError(_("Las tarjas de origen deben estar validadas."))
        if any(package.step_tag_state != "created" or package.step_tag_line_ids for package in targets):
            raise ValidationError(_("Las tarjas de destino deben estar creadas y sin detalle previo."))
        if any(line.product_id not in line.source_package_id.step_tag_line_ids.mapped("product_id")
               or line.producer_id not in line.source_package_id.step_tag_line_ids.mapped("producer_id")
               for line in self.line_ids):
            raise ValidationError(_("Producto y productor deben provenir del detalle de la tarja de origen."))
        expected = defaultdict(lambda: [0.0, 0.0, 0.0])
        actual = defaultdict(lambda: [0.0, 0.0, 0.0])
        for package in sources:
            for line in package.step_tag_line_ids:
                values = expected[(package.id, line.producer_id.id, line.product_id.id)]
                values[0] += line.quantity
                values[1] += line.boxes
                values[2] += line.kilos
        for line in self.line_ids:
            key = (line.source_package_id.id, line.producer_id.id, line.product_id.id)
            values = actual[key]
            values[0] += line.quantity
            values[1] += line.boxes
            values[2] += line.kilos
        if expected.keys() != actual.keys() or any(
            float_compare(actual[key][i], expected[key][i], precision_digits=2)
            for key in expected for i in range(3)
        ):
            raise ValidationError(_("La cantidad, cajas y kilos de origen deben entrar íntegros en otras tarjas."))
        locations = sources.mapped("quant_ids.location_id")
        if len(locations) != 1 or locations.usage != "internal":
            raise ValidationError(_("Las tarjas de origen deben estar en una misma ubicación interna."))
        quant = self.env["stock.quant"]
        for line in self.line_ids:
            available = quant._get_available_quantity(
                line.product_id, locations, package_id=line.source_package_id, strict=True)
            if float_compare(available, line.quantity, precision_digits=2) < 0:
                raise ValidationError(_("No hay existencias suficientes en la tarja %s.") % line.source_package_id.name)
        return locations

    def action_validate(self):
        for repack in self:
            location = repack._check_repack()
            warehouse = self.env["stock.warehouse"].search([
                ("company_id", "=", repack.company_id.id),
                ("lot_stock_id", "child_of", location.id),
            ], limit=1)
            if not warehouse:
                warehouse = self.env["stock.warehouse"].search([
                    ("company_id", "=", repack.company_id.id)], limit=1)
            if not warehouse:
                raise ValidationError(_("Configure una bodega para repaletizar."))
            for target in repack.line_ids.mapped("target_package_id"):
                source = repack.line_ids.filtered(lambda line: line.target_package_id == target)[0].source_package_id
                grouped = defaultdict(lambda: [0.0, 0.0, 0.0])
                for line in repack.line_ids.filtered(lambda line: line.target_package_id == target):
                    values = grouped[(line.producer_id.id, line.product_id.id)]
                    values[0] += line.quantity
                    values[1] += line.boxes
                    values[2] += line.kilos
                target.write({
                    "fundo_id": source.fundo_id.id,
                    "step_producer_id": source.step_producer_id.id,
                    "box_count": round(sum(line.boxes for line in repack.line_ids.filtered(
                        lambda line: line.target_package_id == target))),
                    "step_tag_line_ids": [(0, 0, {
                        "producer_id": producer_id, "product_id": product_id,
                        "quantity": values[0], "boxes": values[1], "kilos": values[2],
                    }) for (producer_id, product_id), values in grouped.items()],
                })
            picking = self.env["stock.picking"].create({
                "picking_type_id": warehouse.int_type_id.id,
                "company_id": repack.company_id.id,
                "origin": repack.name,
                "location_id": location.id,
                "location_dest_id": location.id,
                "move_ids": [(0, 0, {
                    "name": line.product_id.display_name,
                    "product_id": line.product_id.id,
                    "product_uom_qty": line.quantity,
                    "product_uom": line.product_id.uom_id.id,
                    "location_id": location.id,
                    "location_dest_id": location.id,
                }) for line in repack.line_ids],
            })
            picking.action_confirm()
            # action_confirm may merge moves for the same product. Keep one
            # move line per source/target pair so no producer's boxes vanish.
            for line in repack.line_ids:
                move = picking.move_ids.filtered(lambda row: row.product_id == line.product_id)
                if len(move) != 1:
                    raise ValidationError(_("No se encontró un movimiento único para %s.") % line.product_id.display_name)
                self.env["stock.move.line"].create({
                    "move_id": move.id, "picking_id": picking.id,
                    "product_id": line.product_id.id,
                    "product_uom_id": line.product_id.uom_id.id,
                    "quantity": line.quantity,
                    "location_id": location.id, "location_dest_id": location.id,
                    "package_id": line.source_package_id.id,
                    "result_package_id": line.target_package_id.id,
                })
            picking.button_validate()
            if picking.state != "done":
                raise UserError(_("Complete el traslado de repaletizado en Inventario."))
            repack.line_ids.mapped("source_package_id").write({"step_tag_state": "repalletized"})
            for target in repack.line_ids.mapped("target_package_id"):
                target.action_step_validate_tag()
            repack.write({"picking_id": picking.id, "state": "done"})
        return True


class PackingRepackLine(models.Model):
    _name = "step.packing.repack.line"
    _description = "Distribución de repaletizado"

    repack_id = fields.Many2one("step.packing.repack", required=True, ondelete="cascade")
    source_package_id = fields.Many2one("stock.quant.package", string="Tarja origen", required=True)
    target_package_id = fields.Many2one("stock.quant.package", string="Tarja destino", required=True)
    producer_id = fields.Many2one("res.partner", string="Productor", required=True)
    product_id = fields.Many2one("product.product", string="Producto", required=True)
    quantity = fields.Float(string="Cantidad", required=True, digits="Product Unit of Measure")
    boxes = fields.Float(string="Cajas", required=True, digits="Product Unit of Measure")
    kilos = fields.Float(string="Kilos", required=True, digits="Stock Weight")

    @api.model_create_multi
    def create(self, vals_list):
        records = self.env["step.packing.repack"].browse([vals["repack_id"] for vals in vals_list if vals.get("repack_id")])
        if any(record.state != "draft" for record in records):
            raise UserError(_("No agregue líneas a un repaletizado validado."))
        return super().create(vals_list)

    def write(self, vals):
        if vals and any(line.repack_id.state != "draft" for line in self):
            raise UserError(_("No modifique líneas de un repaletizado validado."))
        return super().write(vals)

    def unlink(self):
        if any(line.repack_id.state != "draft" for line in self):
            raise UserError(_("No elimine líneas de un repaletizado validado."))
        return super().unlink()

    @api.constrains("quantity", "boxes", "kilos")
    def _check_positive(self):
        for line in self:
            if min(line.quantity, line.boxes, line.kilos) <= 0:
                raise ValidationError(_("Cantidad, cajas y kilos deben ser positivos."))
