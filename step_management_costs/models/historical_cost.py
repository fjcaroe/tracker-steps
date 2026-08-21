from odoo import api, fields, models


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
    actual_amount = fields.Monetary(string="Valor real", currency_field="currency_id")
    budget_amount = fields.Monetary(string="Valor presupuestado", currency_field="currency_id")
    variance = fields.Monetary(
        string="Desviación", compute="_compute_variance", store=True, currency_field="currency_id"
    )
    variance_percent = fields.Float(string="Desviación %", compute="_compute_variance", store=True)
    notes = fields.Char(string="Observación")

    @api.depends("actual_amount", "budget_amount")
    def _compute_variance(self):
        for record in self:
            record.variance = record.actual_amount - record.budget_amount
            record.variance_percent = (
                record.variance * 100.0 / record.budget_amount if record.budget_amount else 0.0
            )
