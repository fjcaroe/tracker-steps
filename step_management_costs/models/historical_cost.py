from odoo import api, fields, models

from .exchange_rate import default_conversion_currency


class StepManagementHistoricalCost(models.Model):
    _name = "step.management.historical.cost"
    _description = "Costo histórico operacional"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(string="Descripción", required=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    date = fields.Date(string="Mes / fecha", required=True, index=True)
    center_id = fields.Many2one("step.management.cost.center", string="Centro de costo", required=True, index=True)
    group_id = fields.Many2one("step.management.budget.group", string="Grupo presupuestario", index=True)
    indicator = fields.Char(string="Indicador / labor")
    quantity = fields.Float(string="Cantidad / jornadas", digits=(16, 4))
    currency_id = fields.Many2one(
        "res.currency", required=True, default=lambda self: self.env.company.currency_id
    )
    conversion_currency_id = fields.Many2one(
        "res.currency", string="Convertir a",
        default=lambda self: default_conversion_currency(self.env),
        domain="[('active', '=', True)]",
    )
    conversion_rate_type = fields.Selection(
        [("actual", "Real Odoo"), ("estimated", "Estimado mensual")],
        string="Tipo de conversión", default="actual", required=True,
    )
    actual_amount = fields.Monetary(string="Valor real", currency_field="currency_id")
    budget_amount = fields.Monetary(string="Valor presupuestado", currency_field="currency_id")
    variance = fields.Monetary(
        string="Desviación", compute="_compute_variance", store=True, currency_field="currency_id"
    )
    variance_percent = fields.Float(string="Desviación %", compute="_compute_variance", store=True)
    conversion_available = fields.Boolean(compute="_compute_conversion")
    conversion_factor = fields.Float(
        string="Factor origen → destino", compute="_compute_conversion", digits=(16, 10)
    )
    conversion_target_value = fields.Float(
        string="Valor moneda destino", compute="_compute_conversion", digits=(16, 6)
    )
    actual_amount_converted = fields.Monetary(
        string="Real convertido", compute="_compute_conversion",
        currency_field="conversion_currency_id",
    )
    budget_amount_converted = fields.Monetary(
        string="Presupuestado convertido", compute="_compute_conversion",
        currency_field="conversion_currency_id",
    )
    variance_converted = fields.Monetary(
        string="Desviación convertida", compute="_compute_conversion",
        currency_field="conversion_currency_id",
    )
    notes = fields.Char(string="Observación")

    @api.depends("actual_amount", "budget_amount")
    def _compute_variance(self):
        for record in self:
            record.variance = record.actual_amount - record.budget_amount
            record.variance_percent = (
                record.variance * 100.0 / record.budget_amount if record.budget_amount else 0.0
            )

    @api.depends(
        "actual_amount", "budget_amount", "variance", "currency_id",
        "conversion_currency_id", "conversion_rate_type", "date", "company_id",
    )
    def _compute_conversion(self):
        service = self.env["step.management.exchange.rate"]
        for record in self:
            actual_result = service.get_conversion(
                record.actual_amount, record.currency_id, record.conversion_currency_id,
                record.company_id, record.date, record.conversion_rate_type,
            )
            budget_result = service.get_conversion(
                record.budget_amount, record.currency_id, record.conversion_currency_id,
                record.company_id, record.date, record.conversion_rate_type,
            )
            variance_result = service.get_conversion(
                record.variance, record.currency_id, record.conversion_currency_id,
                record.company_id, record.date, record.conversion_rate_type,
            )
            record.conversion_available = actual_result["available"]
            record.conversion_factor = actual_result["factor"]
            record.conversion_target_value = actual_result["target_value"]
            record.actual_amount_converted = actual_result["amount"]
            record.budget_amount_converted = budget_result["amount"]
            record.variance_converted = variance_result["amount"]
