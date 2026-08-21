from odoo import api, fields, models
from odoo.exceptions import ValidationError


MONTH_FIELDS = [
    "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec", "jan", "feb", "mar", "apr"
]


class StepManagementBudgetTemplate(models.Model):
    _name = "step.management.budget.template"
    _description = "Plantilla de presupuesto operacional"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "active desc, name"

    name = fields.Char(string="Nombre", required=True, tracking=True)
    version = fields.Char(string="Versión", default="1.0", required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True, default=lambda self: self.env.company,
        index=True, tracking=True,
    )
    currency_id = fields.Many2one(
        "res.currency", string="Moneda", required=True,
        default=lambda self: self.env.company.currency_id,
    )
    base_hectares = fields.Float(
        string="Hectáreas base", default=1.0, required=True, digits=(16, 4),
        help="Las cantidades de la plantilla se expresan para esta superficie. Normalmente debe ser 1 hectárea.",
    )
    species = fields.Char(string="Especie / uso")
    expected_yield_kg_ha = fields.Float(string="Rendimiento esperado (kg/ha)")
    notes = fields.Html(string="Descripción y supuestos")
    line_ids = fields.One2many("step.management.budget.template.line", "template_id", string="Indicadores")
    total_per_ha = fields.Monetary(
        string="Costo por hectárea", compute="_compute_totals", store=True, currency_field="currency_id"
    )
    line_count = fields.Integer(string="Cantidad de indicadores", compute="_compute_totals", store=True)
    state = fields.Selection(
        [("draft", "Borrador"), ("active", "Vigente"), ("archived", "Archivada")],
        default="draft", required=True, tracking=True, index=True,
    )
    active = fields.Boolean(default=True)

    @api.depends("line_ids.cost_per_ha")
    def _compute_totals(self):
        for record in self:
            record.total_per_ha = sum(record.line_ids.mapped("cost_per_ha"))
            record.line_count = len(record.line_ids)

    @api.constrains("base_hectares")
    def _check_base_hectares(self):
        for record in self:
            if record.base_hectares <= 0:
                raise ValidationError("Las hectáreas base deben ser mayores que cero.")

    def action_activate(self):
        self.write({"state": "active"})

    def action_set_draft(self):
        self.write({"state": "draft"})

    def action_archive_template(self):
        self.write({"state": "archived", "active": False})


class StepManagementBudgetTemplateLine(models.Model):
    _name = "step.management.budget.template.line"
    _description = "Indicador de plantilla presupuestaria"
    _order = "sequence, id"

    template_id = fields.Many2one(
        "step.management.budget.template", required=True, ondelete="cascade", index=True
    )
    sequence = fields.Integer(default=10)
    category = fields.Selection(
        [("labor", "Mano de obra"), ("input", "Insumo agrícola"),
         ("machinery", "Maquinaria"), ("service", "Servicio"), ("other", "Otro")],
        string="Categoría", required=True, default="labor",
    )
    group_id = fields.Many2one(
        "step.management.budget.group", string="Grupo presupuestario", required=True,
        domain="[('company_id', '=', parent.company_id)]",
    )
    indicator = fields.Char(string="Indicador / labor", required=True)
    activity = fields.Char(string="Actividad")
    product_id = fields.Many2one("product.product", string="Producto")
    uom_id = fields.Many2one("uom.uom", string="Unidad de medida")
    base_quantity = fields.Float(
        string="Cantidad base", digits=(16, 4),
        help="Cantidad para la superficie base de la plantilla cuando no se distribuye por mes.",
    )
    unit_price = fields.Monetary(string="Tarifa unitaria", currency_field="currency_id")
    currency_id = fields.Many2one(related="template_id.currency_id", store=True)
    may = fields.Float(string="May", digits=(16, 4))
    jun = fields.Float(string="Jun", digits=(16, 4))
    jul = fields.Float(string="Jul", digits=(16, 4))
    aug = fields.Float(string="Ago", digits=(16, 4))
    sep = fields.Float(string="Sep", digits=(16, 4))
    oct = fields.Float(string="Oct", digits=(16, 4))
    nov = fields.Float(string="Nov", digits=(16, 4))
    dec = fields.Float(string="Dic", digits=(16, 4))
    jan = fields.Float(string="Ene", digits=(16, 4))
    feb = fields.Float(string="Feb", digits=(16, 4))
    mar = fields.Float(string="Mar", digits=(16, 4))
    apr = fields.Float(string="Abr", digits=(16, 4))
    quantity_per_ha = fields.Float(
        string="Total por hectárea", compute="_compute_amounts", store=True, digits=(16, 4)
    )
    cost_per_ha = fields.Monetary(
        string="Costo por hectárea", compute="_compute_amounts", store=True, currency_field="currency_id"
    )
    notes = fields.Char(string="Supuesto")

    @api.depends("base_quantity", "unit_price", "template_id.base_hectares", *MONTH_FIELDS)
    def _compute_amounts(self):
        for record in self:
            monthly = sum(record[field_name] or 0.0 for field_name in MONTH_FIELDS)
            base_quantity = monthly if monthly else record.base_quantity
            base_hectares = record.template_id.base_hectares or 1.0
            record.quantity_per_ha = base_quantity / base_hectares
            record.cost_per_ha = record.quantity_per_ha * record.unit_price

    @api.constrains("base_quantity", "unit_price", *MONTH_FIELDS)
    def _check_non_negative(self):
        for record in self:
            values = [record.base_quantity, record.unit_price] + [record[name] for name in MONTH_FIELDS]
            if any(value < 0 for value in values):
                raise ValidationError("Las cantidades mensuales, cantidades base y tarifas no pueden ser negativas.")
