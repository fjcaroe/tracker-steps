"""Cuadratura de la OT sobre Fabricación y las tarjas reales de Inventario."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


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
    _inherit = "mrp.production"

    step_packing_order_id = fields.Many2one("step.packing.order", string="Orden de proceso", index=True)
    step_packing_state = fields.Selection([
        ("created", "Creada"), ("validated", "Validada"),
        ("closed", "Cerrada"), ("costed", "Costeada"),
        ("accounted", "Contabilizada"),
    ], default="created", string="Etapa Packing", copy=False, tracking=True)
    step_packing_input_tag_ids = fields.Many2many(
        "stock.quant.package", relation="step_packing_input_tag_rel",
        string="Tarjas C a proceso")
    step_packing_output_tag_ids = fields.Many2many(
        "stock.quant.package", relation="step_packing_output_tag_rel",
        string="Tarjas E/N resultantes")
    step_packing_line_id = fields.Many2one("step.packing.line", string="Línea de proceso")
    step_packing_input_kg = fields.Float(compute="_compute_packing_balance", string="Kilos a proceso", digits="Stock Weight")
    step_packing_export_kg = fields.Float(compute="_compute_packing_balance", string="Kilos exportación", digits="Stock Weight")
    step_packing_commercial_kg = fields.Float(compute="_compute_packing_balance", string="Kilos comercial", digits="Stock Weight")
    step_packing_precaliber_kg = fields.Float(compute="_compute_packing_balance", string="Kilos precalibre", digits="Stock Weight")
    step_packing_waste_kg = fields.Float(compute="_compute_packing_balance", string="Kilos desecho", digits="Stock Weight")
    step_packing_loss_kg = fields.Float(compute="_compute_packing_balance", string="Merma kg", digits="Stock Weight")

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
                ("step_packing_state", "in", ["validated", "closed", "costed", "accounted"]),
                ("step_packing_input_tag_ids", "in", inputs.ids),
            ], limit=1)
            if duplicate:
                raise ValidationError(_("Una tarja C ya está asignada a otra OT validada."))
            duplicate_output = self.search([
                ("id", "!=", production.id),
                ("step_packing_state", "in", ["validated", "closed", "costed", "accounted"]),
                ("step_packing_output_tag_ids", "in", outputs.ids),
            ], limit=1)
            if duplicate_output:
                raise ValidationError(_("Una tarja de salida ya está asignada a otra OT validada."))

    def action_step_packing_validate(self):
        for production in self:
            if production.step_packing_state != "created" or production.state in ("done", "cancel"):
                raise UserError(_("Solo se puede validar una OT creada y activa."))
            production._check_packing_tags()
            production.write({
                "step_packing_state": "validated",
                "fruit_grower_id": production.step_packing_input_tag_ids[0].step_tag_line_ids[0].producer_id.id,
                "fruit_variety_id": production.step_packing_input_tag_ids[0].variedad_id.id,
            })
        return True

    def action_step_packing_close(self):
        for production in self:
            if production.step_packing_state != "validated" or production.state != "done":
                raise UserError(_("Termine la fabricación en Inventario antes de cerrar la OT de Packing."))
            input_packages = production.move_raw_ids.move_line_ids.mapped("package_id")
            output_packages = production.move_finished_ids.move_line_ids.mapped("result_package_id")
            if not set(production.step_packing_input_tag_ids.ids).issubset(set(input_packages.ids)):
                raise ValidationError(_("Las tarjas C deben figurar en los consumos reales de Fabricación."))
            if not set(production.step_packing_output_tag_ids.ids).issubset(set(output_packages.ids)):
                raise ValidationError(_("Las tarjas E/N deben figurar en las salidas reales de Fabricación."))
            for tag in production.step_packing_output_tag_ids:
                products = set(tag.step_tag_line_ids.mapped("product_id").ids)
                stocked = set(tag.quant_ids.filtered(lambda q: q.quantity > 0).mapped("product_id").ids)
                if not products.issubset(stocked):
                    raise ValidationError(_("La tarja resultante no contiene en stock todos los productos declarados."))
            for tag in production.step_packing_output_tag_ids:
                tag.action_step_validate_tag()
            production.step_packing_input_tag_ids.write({"step_tag_state": "processed"})
            production.step_packing_state = "closed"
        return True
