from odoo import fields, models


class StepManagementBudgetGroup(models.Model):
    _name = "step.management.budget.group"
    _description = "Grupo de presupuesto"
    _order = "code, name"

    name = fields.Char(string="Nombre", required=True)
    code = fields.Char(string="Código", required=True, index=True)
    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True, default=lambda self: self.env.company, index=True,
    )
    parent_id = fields.Many2one("step.management.budget.group", string="Grupo padre", ondelete="restrict")
    account_id = fields.Many2one("account.account", string="Cuenta contable")
    color = fields.Integer(string="Color")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("code_company_unique", "unique(code, company_id)",
         "El código del grupo debe ser único por empresa."),
    ]
