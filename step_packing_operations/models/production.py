"""Orden de Trabajo (OT) de Packing: modelo propio, sin pasar por Fabricación.

La OT consume tarjas C reales y produce tarjas E/N reales mediante
traslados de stock directos (mismo mecanismo que usa el repaletizado:
`stock.picking`/`stock.move.line` con `package_id`/`result_package_id`).
No se crea ninguna `mrp.production`: la lista de materiales (`mrp.bom`) se
usa solo como dato de referencia para calcular el consumo de embalajes de
exportación, igual que hace `step_export` con sus programas de embalaje.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero


class FruitPackage(models.Model):
    _inherit = "stock.quant.package"

    step_packing_result = fields.Selection([
        ("export", "Exportación"), ("commercial", "Comercial"),
        ("precaliber", "Precalibre"), ("waste", "Desecho"),
    ], string="Resultado de Packing")


class PackingProcessType(models.Model):
    _inherit = "step.packing.process.type"

    step_category = fields.Selection([
        ("packing", "Embalaje"), ("correction", "Corrección"),
    ], string="Categoría de proceso", default="packing", required=True)


class PackingProduction(models.Model):
    _name = "step.packing.production"
    _description = "Orden de Trabajo de Packing"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(required=True, copy=False, readonly=True, default="Nuevo")
    state = fields.Selection([
        ("created", "Creada"), ("validated", "Validada"),
        ("closed", "Cerrada"), ("costed", "Costeada"),
        ("accounted", "Contabilizada"),
    ], default="created", required=True, string="Estado", copy=False, tracking=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    step_packing_order_id = fields.Many2one("step.packing.order", string="Orden de proceso", index=True)
    step_packing_line_id = fields.Many2one("step.packing.line", string="Línea de proceso")
    product_id = fields.Many2one("product.product", string="Producto terminado", required=True)
    product_qty = fields.Float(string="Cajas planificadas", digits="Product Unit of Measure")
    product_uom_id = fields.Many2one("uom.uom", string="UdM", required=True,
        default=lambda self: self.env.ref("uom.product_uom_unit"))
    bom_id = fields.Many2one("mrp.bom", string="Lista de materiales",
        domain="[('product_tmpl_id', '=', product_tmpl_id)]")
    product_tmpl_id = fields.Many2one(related="product_id.product_tmpl_id")
    fruit_grower_id = fields.Many2one("res.partner", string="Productor")
    fruit_fundo_id = fields.Many2one("step.fundo", string="Productor - Fundo")
    fruit_species_id = fields.Many2one("step.especie", string="Especie")
    fruit_variety_id = fields.Many2one("step.variedad", string="Variedad",
        domain="[('especie_id', '=?', fruit_species_id)]")
    step_packing_input_tag_ids = fields.Many2many(
        "stock.quant.package", relation="step_packing_input_tag_rel",
        string="Tarjas C a proceso")
    step_packing_output_tag_ids = fields.Many2many(
        "stock.quant.package", relation="step_packing_output_tag_rel",
        string="Tarjas E/N resultantes")
    input_picking_id = fields.Many2one("stock.picking", string="Consumo MP", readonly=True, copy=False)
    output_picking_id = fields.Many2one("stock.picking", string="Salida producto", readonly=True, copy=False)
    material_picking_id = fields.Many2one("stock.picking", string="Consumo materiales", readonly=True, copy=False)
    step_packing_input_kg = fields.Float(compute="_compute_packing_balance", string="Kilos a proceso", digits="Stock Weight")
    step_packing_export_kg = fields.Float(compute="_compute_packing_balance", string="Kilos exportación", digits="Stock Weight")
    step_packing_commercial_kg = fields.Float(compute="_compute_packing_balance", string="Kilos comercial", digits="Stock Weight")
    step_packing_precaliber_kg = fields.Float(compute="_compute_packing_balance", string="Kilos precalibre", digits="Stock Weight")
    step_packing_waste_kg = fields.Float(compute="_compute_packing_balance", string="Kilos desecho", digits="Stock Weight")
    step_packing_loss_kg = fields.Float(compute="_compute_packing_balance", string="Merma kg", digits="Stock Weight")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "Nuevo") == "Nuevo":
                vals["name"] = self.env["ir.sequence"].next_by_code("step.packing.production") or "Nuevo"
        return super().create(vals_list)

    @api.depends("step_packing_input_tag_ids.step_tag_line_ids.kilos",
                 "step_packing_output_tag_ids.step_tag_line_ids.kilos",
                 "step_packing_output_tag_ids.step_packing_result")
    def _compute_packing_balance(self):
        for production in self:
            production.step_packing_input_kg = sum(production.step_packing_input_tag_ids.mapped("step_actual_kg"))
            production.step_packing_export_kg = sum(production.step_packing_output_tag_ids.filtered(
                lambda tag: tag.step_packing_result == "export").mapped("step_actual_kg"))
            production.step_packing_commercial_kg = sum(production.step_packing_output_tag_ids.filtered(
                lambda tag: tag.step_packing_result == "commercial").mapped("step_actual_kg"))
            production.step_packing_precaliber_kg = sum(production.step_packing_output_tag_ids.filtered(
                lambda tag: tag.step_packing_result == "precaliber").mapped("step_actual_kg"))
            production.step_packing_waste_kg = sum(production.step_packing_output_tag_ids.filtered(
                lambda tag: tag.step_packing_result == "waste").mapped("step_actual_kg"))
            production.step_packing_loss_kg = (production.step_packing_input_kg -
                production.step_packing_export_kg - production.step_packing_commercial_kg -
                production.step_packing_precaliber_kg - production.step_packing_waste_kg)

    def _check_packing_tags(self):
        for production in self:
            inputs = production.step_packing_input_tag_ids
            outputs = production.step_packing_output_tag_ids
            if not inputs or not outputs:
                raise ValidationError(_("La OT requiere tarjas C de entrada y tarjas E/N de salida."))
            if inputs & outputs:
                raise ValidationError(_("Una tarja no puede ser entrada y salida de la misma OT."))
            if any(tag.step_tag_kind != "C" or tag.step_tag_state != "validated" for tag in inputs):
                raise ValidationError(_("Las tarjas de entrada deben ser C validadas."))
            if any(tag.step_tag_kind not in ("E", "N") or tag.step_tag_state != "created" for tag in outputs):
                raise ValidationError(_("Las tarjas de salida deben ser E/N creadas."))
            if any(not tag.step_tag_line_ids or not tag.step_packing_result for tag in outputs):
                raise ValidationError(_("Cada tarja de salida requiere detalle y clasificación de resultado."))
            if any((tag.step_tag_kind == "E") != (tag.step_packing_result == "export") for tag in outputs):
                raise ValidationError(_("La exportación usa tarja E; comercial, precalibre y desecho usan N."))
            if len(set((inputs | outputs).mapped("variedad_id").ids)) != 1 or any(not tag.variedad_id for tag in (inputs | outputs)):
                raise ValidationError(_("Todas las tarjas de la OT deben tener la misma variedad."))
            producers = set((inputs | outputs).mapped("step_tag_line_ids.producer_id").ids)
            if len(producers) != 1:
                raise ValidationError(_("El proceso de Packing exige un único productor."))
            if production.fruit_grower_id and production.fruit_grower_id.id not in producers:
                raise ValidationError(_("El productor de la OT no coincide con las tarjas."))
            if production.fruit_variety_id and production.fruit_variety_id != inputs[0].variedad_id:
                raise ValidationError(_("La variedad de la OT no coincide con las tarjas."))
            if production.step_packing_order_id:
                order = production.step_packing_order_id
                if order.state != "validated":
                    raise ValidationError(_("La orden de proceso debe estar validada."))
                if producers & set(order.forbidden_producer_ids.ids):
                    raise ValidationError(_("El productor está restringido por el programa."))
                if inputs[0].variedad_id in order.forbidden_variety_ids:
                    raise ValidationError(_("La variedad está restringida por el programa."))
                if order.company_id != production.company_id:
                    raise ValidationError(_("La orden de proceso pertenece a otra empresa."))
            if float_compare(production.step_packing_input_kg, 0, precision_digits=2) <= 0:
                raise ValidationError(_("Los kilos a proceso deben ser positivos."))
            if float_compare(production.step_packing_loss_kg, 0, precision_digits=2) < 0:
                raise ValidationError(_("La salida supera los kilos ingresados al proceso."))
            duplicate = self.search([
                ("id", "!=", production.id),
                ("state", "in", ["validated", "closed", "costed", "accounted"]),
                ("step_packing_input_tag_ids", "in", inputs.ids),
            ], limit=1)
            if duplicate:
                raise ValidationError(_("Una tarja C ya está asignada a otra OT validada."))
            duplicate_output = self.search([
                ("id", "!=", production.id),
                ("state", "in", ["validated", "closed", "costed", "accounted"]),
                ("step_packing_output_tag_ids", "in", outputs.ids),
            ], limit=1)
            if duplicate_output:
                raise ValidationError(_("Una tarja de salida ya está asignada a otra OT validada."))

    def action_step_packing_validate(self):
        for production in self:
            if production.state != "created":
                raise UserError(_("Solo se puede validar una OT creada."))
            production._check_packing_tags()
            production.write({
                "state": "validated",
                "fruit_grower_id": production.step_packing_input_tag_ids[0].step_tag_line_ids[0].producer_id.id,
                "fruit_variety_id": production.step_packing_input_tag_ids[0].variedad_id.id,
            })
        return True

    def _production_location(self):
        self.ensure_one()
        location = self.env["stock.location"].search([
            ("usage", "=", "production"), ("company_id", "=", self.company_id.id)], limit=1)
        if not location:
            raise ValidationError(_("No existe la ubicación virtual de Producción para %s.") % self.company_id.display_name)
        return location

    def _packing_stock_location(self, tags):
        locations = tags.mapped("quant_ids").filtered(lambda quant: quant.quantity > 0).mapped("location_id")
        if len(locations) != 1 or locations.usage != "internal":
            raise ValidationError(_("Las tarjas deben tener existencias en una única ubicación interna."))
        return locations

    def _create_packing_move(self, warehouse, source, dest, lines):
        """lines: list of (product, qty, source_package_or_False, result_package_or_False)."""
        self.ensure_one()
        grouped = {}
        for product, qty, src_pkg, dst_pkg in lines:
            grouped.setdefault(product, 0.0)
            grouped[product] += qty
        picking = self.env["stock.picking"].create({
            "picking_type_id": warehouse.int_type_id.id,
            "company_id": self.company_id.id,
            "origin": self.name,
            "location_id": source.id,
            "location_dest_id": dest.id,
            "move_ids": [(0, 0, {
                "name": product.display_name, "product_id": product.id,
                "product_uom_qty": qty, "product_uom": product.uom_id.id,
                "location_id": source.id, "location_dest_id": dest.id,
            }) for product, qty in grouped.items()],
        })
        picking.action_confirm()
        for product, qty, src_pkg, dst_pkg in lines:
            move = picking.move_ids.filtered(lambda row: row.product_id == product)
            if len(move) != 1:
                raise ValidationError(_("No se encontró un movimiento único para %s.") % product.display_name)
            self.env["stock.move.line"].create({
                "move_id": move.id, "picking_id": picking.id,
                "product_id": product.id, "product_uom_id": product.uom_id.id,
                "quantity": qty, "location_id": source.id, "location_dest_id": dest.id,
                "package_id": src_pkg.id if src_pkg else False,
                "result_package_id": dst_pkg.id if dst_pkg else False,
            })
        picking.button_validate()
        if picking.state != "done":
            raise UserError(_("No se pudo completar el movimiento de Packing en Inventario."))
        return picking

    def _consume_packaging_materials(self, warehouse, location, production_location):
        """Usa la BOM solo como dato de referencia (igual que step_export), sin crear
        ninguna mrp.production: calcula cajas de exportación x consumo unitario y
        genera un único traslado de salida de materiales."""
        self.ensure_one()
        if not self.bom_id:
            return self.env["stock.picking"]
        export_boxes = sum(
            self.step_packing_output_tag_ids.filtered(lambda tag: tag.step_packing_result == "export")
            .mapped("step_tag_line_ids.boxes"))
        if float_is_zero(export_boxes, precision_digits=2):
            return self.env["stock.picking"]
        factor = export_boxes / (self.bom_id.product_qty or 1.0)
        lines = []
        for component in self.bom_id.bom_line_ids:
            qty = component.product_uom_id._compute_quantity(component.product_qty * factor, component.product_id.uom_id)
            if float_is_zero(qty, precision_digits=2):
                continue
            lines.append((component.product_id, qty, False, False))
        if not lines:
            return self.env["stock.picking"]
        return self._create_packing_move(warehouse, location, production_location, lines)

    def action_step_packing_close(self):
        for production in self:
            if production.state != "validated":
                raise UserError(_("Valide la OT antes de cerrarla."))
            warehouse = self.env["stock.warehouse"].search([
                ("company_id", "=", production.company_id.id)], limit=1)
            if not warehouse:
                raise ValidationError(_("Configure una bodega para cerrar la OT de Packing."))
            production_location = production._production_location()
            location = production._packing_stock_location(production.step_packing_input_tag_ids)

            # 1) Consumo de materia prima: las tarjas C salen de la bodega hacia Producción.
            consume_lines = []
            for tag in production.step_packing_input_tag_ids:
                for quant in tag.quant_ids.filtered(lambda q: q.quantity > 0):
                    consume_lines.append((quant.product_id, quant.quantity, tag, False))
            if not consume_lines:
                raise ValidationError(_("Las tarjas de entrada no tienen existencias reales."))
            input_picking = production._create_packing_move(warehouse, location, production_location, consume_lines)

            # 2) Consumo de materiales de embalaje (solo tarjas de exportación), BOM como referencia.
            material_picking = production._consume_packaging_materials(warehouse, location, production_location)

            # 3) Salida de producto terminado: las tarjas E/N entran a bodega desde Producción.
            produce_lines = []
            for tag in production.step_packing_output_tag_ids:
                for line in tag.step_tag_line_ids:
                    produce_lines.append((line.product_id, line.quantity, False, tag))
            output_picking = production._create_packing_move(warehouse, production_location, location, produce_lines)

            for tag in production.step_packing_output_tag_ids:
                products = set(tag.step_tag_line_ids.mapped("product_id").ids)
                stocked = set(tag.quant_ids.filtered(lambda q: q.quantity > 0).mapped("product_id").ids)
                if not products.issubset(stocked):
                    raise ValidationError(_("La tarja resultante no contiene en stock todos los productos declarados."))
                tag.action_step_validate_tag()
            production.step_packing_input_tag_ids.write({"step_tag_state": "processed"})
            production.write({
                "state": "closed",
                "input_picking_id": input_picking.id,
                "output_picking_id": output_picking.id,
                "material_picking_id": material_picking.id if material_picking else False,
            })
        return True
