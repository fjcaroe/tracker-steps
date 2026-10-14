"""Packaging valuation and material demand from the active sales programme."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ExportBOM(models.Model):
    _inherit = "mrp.bom"

    step_export_fruit = fields.Boolean(string="Lista para embalaje de fruta")
    step_export_boxes_per_pallet = fields.Float(string="Cajas por pallet")


class ExportBOMLine(models.Model):
    _inherit = "mrp.bom.line"

    step_export_qty_per_pallet = fields.Float(string="Cantidad por pallet")


class ExportPaymentConcept(models.Model):
    _inherit = "step.export.payment.concept"

    standard_cost_per_kg = fields.Float(string="Costo estándar por kg", digits=(16, 4))
    standard_cost_per_box = fields.Float(string="Costo estándar por caja", digits=(16, 4))
    standard_cost_per_pallet = fields.Float(string="Costo estándar por pallet", digits=(16, 4))

    def write(self, vals):
        if {"standard_cost_per_kg", "standard_cost_per_box", "standard_cost_per_pallet"}.intersection(vals):
            if self.env["step.export.packaging.cost"].search_count([
                ("concept_id", "in", self.ids), ("program_id.state", "=", "valued")]):
                raise UserError(_("El costo estándar ya se usó en un programa valorizado."))
        return super().write(vals)


class PackagingProgram(models.Model):
    _name = "step.export.packaging.program"
    _description = "Programa de embalajes"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(required=True)
    state = fields.Selection([
        ("draft", "Creado"), ("validated", "Validado"),
        ("valued", "Valorizado"),
    ], default="draft", required=True, tracking=True)
    sales_program_id = fields.Many2one("step.export.sales.program", required=True)
    company_id = fields.Many2one(related="sales_program_id.company_id", store=True)
    season_id = fields.Many2one(related="sales_program_id.season_id", store=True)
    species_id = fields.Many2one(related="sales_program_id.species_id", store=True)
    product_id = fields.Many2one(related="sales_program_id.product_id", store=True)
    bom_id = fields.Many2one("mrp.bom", string="Lista de materiales")
    usd_currency_id = fields.Many2one("res.currency", default=lambda self: self.env.ref("base.USD"))
    cost_line_ids = fields.One2many("step.export.packaging.cost", "program_id", string="Servicios y costos")
    material_line_ids = fields.One2many("step.export.packaging.material", "program_id", string="Materiales")
    kg_qty = fields.Float(related="sales_program_id.kg_qty", store=True)
    box_qty = fields.Float(related="sales_program_id.box_qty", store=True)
    pallet_qty = fields.Float(related="sales_program_id.pallet_qty", store=True)
    standard_cost_usd = fields.Monetary(currency_field="usd_currency_id", compute="_compute_cost", store=True)

    _sql_constraints = [
        ("packaging_sales_version_unique", "unique(sales_program_id)",
         "Esta versión de programa de ventas ya tiene programa de embalajes."),
    ]

    @api.depends("cost_line_ids.amount_usd", "material_line_ids.amount_usd")
    def _compute_cost(self):
        for record in self:
            record.standard_cost_usd = (sum(record.cost_line_ids.mapped("amount_usd")) +
                                        sum(record.material_line_ids.mapped("amount_usd")))

    def action_validate(self):
        for record in self:
            if record.state != "draft" or record.sales_program_id.state != "current":
                raise UserError(_("Seleccione un programa de ventas vigente y creado."))
            if not record.cost_line_ids:
                raise ValidationError(_("Ingrese al menos un concepto de valorización."))
            record.state = "validated"
        return True

    def action_value(self):
        for record in self:
            if record.state != "validated" or not record.bom_id:
                raise UserError(_("Valide el programa y seleccione una lista de materiales."))
            if not record.bom_id.step_export_fruit:
                raise ValidationError(_("La lista de materiales debe estar marcada para fruta."))
            if record.bom_id.product_tmpl_id != record.product_id.product_tmpl_id:
                raise ValidationError(_("La lista de materiales debe corresponder al producto del programa."))
            if record.bom_id.product_qty <= 0:
                raise ValidationError(_("La cantidad base de la lista de materiales debe ser positiva."))
            material_lines = []
            for bom_line in record.bom_id.bom_line_ids:
                boxes_qty = record.box_qty * bom_line.product_qty / record.bom_id.product_qty
                pallet_qty = record.pallet_qty * bom_line.step_export_qty_per_pallet
                material_lines.append((0, 0, {
                    "bom_line_id": bom_line.id, "product_id": bom_line.product_id.id,
                    "box_consumption": boxes_qty, "pallet_consumption": pallet_qty,
                    "unit_cost_usd": bom_line.product_id.standard_price *
                        record.company_id.currency_id._convert(1, record.usd_currency_id,
                                                               record.company_id, fields.Date.today()),
                }))
            record.write({"material_line_ids": [(5, 0, 0)] + material_lines, "state": "valued"})
        return True

    def write(self, vals):
        if {"sales_program_id", "cost_line_ids", "bom_id", "material_line_ids"}.intersection(vals):
            if any(record.state == "valued" for record in self):
                raise UserError(_("El programa valorizado conserva su cálculo histórico."))
        return super().write(vals)


class PackagingCost(models.Model):
    _name = "step.export.packaging.cost"
    _description = "Costo estándar de programa de embalajes"

    program_id = fields.Many2one("step.export.packaging.program", required=True, ondelete="cascade")
    concept_id = fields.Many2one("step.export.payment.concept", required=True)
    usd_currency_id = fields.Many2one(related="program_id.usd_currency_id")
    amount_usd = fields.Monetary(currency_field="usd_currency_id", compute="_compute_amount", store=True)

    @api.depends("concept_id.standard_cost_per_kg", "concept_id.standard_cost_per_box",
                 "concept_id.standard_cost_per_pallet", "program_id.kg_qty",
                 "program_id.box_qty", "program_id.pallet_qty")
    def _compute_amount(self):
        for record in self:
            concept = record.concept_id
            program = record.program_id
            record.amount_usd = (concept.standard_cost_per_kg * program.kg_qty +
                                 concept.standard_cost_per_box * program.box_qty +
                                 concept.standard_cost_per_pallet * program.pallet_qty)


class PackagingMaterial(models.Model):
    _name = "step.export.packaging.material"
    _description = "Necesidad de material de embalaje"

    program_id = fields.Many2one("step.export.packaging.program", required=True, ondelete="cascade")
    bom_line_id = fields.Many2one("mrp.bom.line", required=True)
    product_id = fields.Many2one("product.product", required=True)
    box_consumption = fields.Float(string="Consumo cajas")
    pallet_consumption = fields.Float(string="Consumo pallet")
    standard_consumption = fields.Float(compute="_compute_consumption", store=True)
    available_qty = fields.Float(related="product_id.qty_available", string="Stock disponible")
    shortage_qty = fields.Float(compute="_compute_shortage")
    unit_cost_usd = fields.Float(string="Costo estándar USD", digits=(16, 4))
    usd_currency_id = fields.Many2one(related="program_id.usd_currency_id")
    amount_usd = fields.Monetary(currency_field="usd_currency_id", compute="_compute_consumption", store=True)

    @api.depends("box_consumption", "pallet_consumption", "unit_cost_usd")
    def _compute_consumption(self):
        for record in self:
            record.standard_consumption = record.box_consumption + record.pallet_consumption
            record.amount_usd = record.standard_consumption * record.unit_cost_usd

    @api.depends("standard_consumption", "available_qty")
    def _compute_shortage(self):
        for record in self:
            record.shortage_qty = max(0, record.standard_consumption - record.available_qty)

    def action_purchase(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "res_model": "purchase.order", "view_mode": "form",
            "target": "current", "context": {"default_order_line": [(0, 0, {
                "product_id": self.product_id.id, "product_qty": self.shortage_qty,
                "product_uom": self.product_id.uom_po_id.id,
            })]},
        }
