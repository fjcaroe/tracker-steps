"""Programa semanal y necesidades de materiales para Packing (T41)."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class PackingOrder(models.Model):
    _name = "step.packing.order"
    _description = "Orden de proceso de Packing"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "week_start desc, id desc"
    _check_company_auto = True

    name = fields.Char(required=True, copy=False, readonly=True, default="Nuevo")
    state = fields.Selection([
        ("draft", "Creada"), ("validated", "Validada"),
        ("closed", "Cerrada"),
    ], default="draft", required=True, tracking=True, copy=False)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    week_start = fields.Date(string="Inicio semana", required=True, default=fields.Date.today)
    week_end = fields.Date(string="Fin semana", required=True)
    sales_program_id = fields.Many2one("step.export.sales.program", string="Programa de ventas", check_company=True)
    packing_partner_id = fields.Many2one("res.partner", string="Packing", domain="[('step_export_packing','=',True)]")
    instruction = fields.Html(string="Instructivo de embalaje")
    line_ids = fields.One2many("step.packing.order.line", "order_id", string="Detalle", copy=True)
    material_need_ids = fields.One2many("step.packing.material.need", "order_id", string="Necesidad de materiales", copy=False)
    forbidden_producer_ids = fields.Many2many("res.partner", relation="step_packing_order_forbidden_producer_rel",
        string="Productores restringidos")
    forbidden_variety_ids = fields.Many2many("step.variedad", relation="step_packing_order_forbidden_variety_rel",
        string="Variedades restringidas")
    production_ids = fields.One2many("step.packing.production", "step_packing_order_id", string="Órdenes de trabajo")
    planned_boxes = fields.Float(compute="_compute_planned", string="Cajas planificadas")
    planned_kg = fields.Float(compute="_compute_planned", string="Kilos planificados", digits="Stock Weight")

    @api.depends("line_ids.boxes", "line_ids.kilos")
    def _compute_planned(self):
        for order in self:
            order.planned_boxes = sum(order.line_ids.mapped("boxes"))
            order.planned_kg = sum(order.line_ids.mapped("kilos"))

    @api.constrains("week_start", "week_end")
    def _check_week(self):
        for order in self:
            if order.week_start and order.week_end and order.week_end < order.week_start:
                raise ValidationError(_("El fin de la semana no puede ser anterior al inicio."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "Nuevo") == "Nuevo":
                vals["name"] = self.env["ir.sequence"].next_by_code("step.packing.order") or "Nuevo"
        return super().create(vals_list)

    def write(self, vals):
        protected = {"week_start", "week_end", "sales_program_id", "packing_partner_id", "line_ids",
                     "forbidden_producer_ids", "forbidden_variety_ids"}
        if protected.intersection(vals) and any(order.state != "draft" for order in self):
            raise UserError(_("Una orden validada no admite cambios de planificación."))
        return super().write(vals)

    def action_validate(self):
        for order in self:
            if order.state != "draft" or not order.line_ids:
                raise UserError(_("La orden debe estar creada y contener productos."))
            if order.sales_program_id and order.sales_program_id.state != "current":
                raise UserError(_("El programa de ventas debe estar vigente."))
            if any(line.boxes <= 0 or line.kilos <= 0 for line in order.line_ids):
                raise ValidationError(_("Cada línea requiere cajas y kilos positivos."))
            order.state = "validated"
        return True

    def action_refresh_materials(self):
        for order in self:
            if order.state == "closed":
                raise UserError(_("No se recalculan materiales de una orden cerrada."))
            needs = {}
            for line in order.line_ids:
                bom = line.bom_id or self.env["mrp.bom"]._bom_find(line.product_id, company_id=order.company_id.id).get(line.product_id)
                if not bom:
                    continue
                factor = line.boxes / bom.product_qty
                for component in bom.bom_line_ids:
                    product = component.product_id
                    qty = component.product_uom_id._compute_quantity(component.product_qty * factor, product.uom_id)
                    needs[product] = needs.get(product, 0.0) + qty
            order.material_need_ids.unlink()
            for product, quantity in needs.items():
                self.env["step.packing.material.need"].create({
                    "order_id": order.id, "product_id": product.id, "required_qty": quantity,
                    "available_qty": product.with_company(order.company_id).free_qty,
                })
        return True

    def action_close(self):
        for order in self:
            if order.state != "validated":
                raise UserError(_("Valide la orden antes de cerrarla."))
            if order.production_ids and any(mo.state != "closed" for mo in order.production_ids):
                raise UserError(_("Cierre primero todas las OT vinculadas."))
            order.state = "closed"
        return True


class PackingOrderLine(models.Model):
    _name = "step.packing.order.line"
    _description = "Producto planificado para Packing"
    _order = "sequence, id"

    order_id = fields.Many2one("step.packing.order", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one("product.product", string="Producto terminado", required=True)
    bom_id = fields.Many2one("mrp.bom", string="Lista de materiales")
    species_id = fields.Many2one("step.especie", string="Especie", required=True)
    variety_id = fields.Many2one("step.variedad", string="Variedad")
    packaging_id = fields.Many2one("product.packaging", string="Embalaje")
    label = fields.Char(string="Etiqueta")
    caliber_id = fields.Many2one("step.management.fruit.caliber", string="Calibre")
    category_id = fields.Many2one("step.management.fruit.category", string="Categoría")
    boxes = fields.Float(string="Cajas", digits="Product Unit of Measure", required=True)
    kilos = fields.Float(string="Kilos", digits="Stock Weight", required=True)
    inspection_type = fields.Char(string="Inspección")

    @api.model_create_multi
    def create(self, vals_list):
        orders = self.env["step.packing.order"].browse([vals["order_id"] for vals in vals_list if vals.get("order_id")])
        if any(order.state != "draft" for order in orders):
            raise UserError(_("No agregue productos a una orden validada."))
        return super().create(vals_list)

    def write(self, vals):
        if vals and any(line.order_id.state != "draft" for line in self):
            raise UserError(_("No modifique productos de una orden validada."))
        return super().write(vals)

    def unlink(self):
        if any(line.order_id.state != "draft" for line in self):
            raise UserError(_("No elimine productos de una orden validada."))
        return super().unlink()

    @api.constrains("boxes", "kilos")
    def _check_positive(self):
        for line in self:
            if float_compare(line.boxes, 0, precision_digits=2) <= 0 or float_compare(line.kilos, 0, precision_digits=2) <= 0:
                raise ValidationError(_("Las cajas y los kilos planificados deben ser positivos."))

    def action_create_production(self):
        self.ensure_one()
        if self.order_id.state != "validated":
            raise UserError(_("Valide la orden de proceso antes de crear la OT."))
        vals = {
            "product_id": self.product_id.id,
            "product_qty": self.boxes,
            "product_uom_id": self.product_id.uom_id.id,
            "step_packing_order_id": self.order_id.id,
            "fruit_species_id": self.species_id.id,
            "fruit_variety_id": self.variety_id.id,
        }
        if self.bom_id:
            vals["bom_id"] = self.bom_id.id
        production = self.env["step.packing.production"].create(vals)
        return {
            "type": "ir.actions.act_window", "res_model": "step.packing.production",
            "res_id": production.id, "view_mode": "form", "target": "current",
        }


class PackingMaterialNeed(models.Model):
    _name = "step.packing.material.need"
    _description = "Necesidad de materiales de Packing"
    _order = "product_id"

    order_id = fields.Many2one("step.packing.order", required=True, ondelete="cascade")
    product_id = fields.Many2one("product.product", required=True)
    required_qty = fields.Float(string="Necesidad", digits="Product Unit of Measure")
    available_qty = fields.Float(string="Disponible al calcular", digits="Product Unit of Measure")
    shortage_qty = fields.Float(string="Faltante", compute="_compute_shortage", digits="Product Unit of Measure")
    uom_id = fields.Many2one(related="product_id.uom_id")

    @api.depends("required_qty", "available_qty")
    def _compute_shortage(self):
        for need in self:
            need.shortage_qty = max(0, need.required_qty - need.available_qty)
