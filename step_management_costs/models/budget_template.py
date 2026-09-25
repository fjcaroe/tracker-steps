from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .exchange_rate import default_conversion_currency


MONTH_FIELDS = [
    "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec", "jan", "feb", "mar", "apr"
]


class StepManagementBudgetTemplate(models.Model):
    _name = "step.management.budget.template"
    _description = "Plantilla de presupuesto operacional"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "active desc, name"
    _check_company_auto = True

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
    conversion_currency_id = fields.Many2one(
        "res.currency", string="Convertir a",
        default=lambda self: default_conversion_currency(self.env),
        domain="[('active', '=', True)]",
    )
    conversion_date = fields.Date(
        string="Mes de conversión", default=fields.Date.context_today,
        help="El año y mes determinan qué valor se toma del maestro de tipos de cambio.",
    )
    conversion_rate_type = fields.Selection(
        [("estimated", "Estimado mensual"), ("actual", "Real Odoo")],
        string="Tipo de conversión", default="estimated", required=True,
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
    conversion_available = fields.Boolean(compute="_compute_conversion")
    conversion_factor = fields.Float(
        string="Factor origen → destino", compute="_compute_conversion", digits=(16, 10)
    )
    conversion_target_value = fields.Float(
        string="Valor moneda destino", compute="_compute_conversion", digits=(16, 6)
    )
    total_per_ha_converted = fields.Monetary(
        string="Costo/ha convertido", compute="_compute_conversion",
        currency_field="conversion_currency_id",
    )
    line_count = fields.Integer(string="Cantidad de indicadores", compute="_compute_totals", store=True)
    state = fields.Selection(
        [("draft", "Borrador"), ("active", "Vigente"), ("archived", "Archivada")],
        default="draft", required=True, tracking=True, index=True,
    )
    active = fields.Boolean(default=True)

    @api.depends("line_ids.cost_per_ha", "line_ids.flow_type")
    def _compute_totals(self):
        for record in self:
            cost_lines = record.line_ids.filtered(lambda line: line.flow_type != "income")
            record.total_per_ha = sum(cost_lines.mapped("cost_per_ha"))
            record.line_count = len(record.line_ids)

    @api.depends(
        "total_per_ha", "currency_id", "conversion_currency_id",
        "conversion_date", "conversion_rate_type", "company_id",
    )
    def _compute_conversion(self):
        service = self.env["step.management.exchange.rate"]
        for record in self:
            result = service.get_conversion(
                record.total_per_ha, record.currency_id, record.conversion_currency_id,
                record.company_id, record.conversion_date, record.conversion_rate_type,
            )
            record.conversion_available = result["available"]
            record.conversion_factor = result["factor"]
            record.conversion_target_value = result["target_value"]
            record.total_per_ha_converted = result["amount"]

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
    _check_company_auto = True

    template_id = fields.Many2one(
        "step.management.budget.template", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        related="template_id.company_id", string="Empresa", store=True, index=True,
    )
    sequence = fields.Integer(default=10)
    category = fields.Selection(
        [("labor", "Mano de obra"), ("input", "Insumo agrícola"),
         ("machinery", "Maquinaria"), ("service", "Servicio"), ("other", "Otro")],
        string="Categoría", required=True, default="labor",
    )
    group_id = fields.Many2one(
        "step.management.budget.group", string="Grupo presupuestario", required=True,
        check_company=True,
        domain="[('company_id', '=', parent.company_id)]",
    )
    flow_type = fields.Selection(
        related="group_id.flow_type", string="Naturaleza", store=True,
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
    conversion_currency_id = fields.Many2one(related="template_id.conversion_currency_id")
    conversion_date = fields.Date(related="template_id.conversion_date")
    conversion_rate_type = fields.Selection(related="template_id.conversion_rate_type")
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
    unit_price_converted = fields.Monetary(
        string="Tarifa convertida", compute="_compute_conversion",
        currency_field="conversion_currency_id",
    )
    cost_per_ha_converted = fields.Monetary(
        string="Costo/ha convertido", compute="_compute_conversion",
        currency_field="conversion_currency_id",
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

    @api.depends(
        "unit_price", "cost_per_ha", "currency_id", "conversion_currency_id",
        "conversion_date", "conversion_rate_type", "template_id.company_id",
    )
    def _compute_conversion(self):
        service = self.env["step.management.exchange.rate"]
        for record in self:
            unit_result = service.get_conversion(
                record.unit_price, record.currency_id, record.conversion_currency_id,
                record.template_id.company_id, record.conversion_date, record.conversion_rate_type,
            )
            cost_result = service.get_conversion(
                record.cost_per_ha, record.currency_id, record.conversion_currency_id,
                record.template_id.company_id, record.conversion_date, record.conversion_rate_type,
            )
            record.unit_price_converted = unit_result["amount"]
            record.cost_per_ha_converted = cost_result["amount"]

    @api.constrains("base_quantity", "unit_price", *MONTH_FIELDS)
    def _check_non_negative(self):
        for record in self:
            values = [record.base_quantity, record.unit_price] + [record[name] for name in MONTH_FIELDS]
            if any(value < 0 for value in values):
                raise ValidationError("Las cantidades mensuales, cantidades base y tarifas no pueden ser negativas.")
