from odoo import api, fields, models
from odoo.exceptions import ValidationError


class StepManagementCostCenter(models.Model):
    _name = "step.management.cost.center"
    _description = "Centro de costo operativo"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "code, name"

    name = fields.Char(string="Nombre", required=True, tracking=True)
    code = fields.Char(string="Código", required=True, index=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True, default=lambda self: self.env.company,
        index=True, tracking=True,
    )
    cost_type = fields.Selection(
        [("crop", "Frutal / cultivo"), ("operational", "Operacional"),
         ("machinery", "Maquinaria"), ("administrative", "Administrativo"), ("other", "Otro")],
        string="Tipo", default="crop", required=True, tracking=True,
    )
    hectares = fields.Float(string="Hectáreas", digits=(16, 4), tracking=True)
    farm = fields.Char(string="Fundo", tracking=True)
    plot = fields.Char(string="Cuartel", tracking=True)
    species = fields.Char(string="Especie", tracking=True)
    variety = fields.Char(string="Variedad", tracking=True)
    analytic_account_id = fields.Many2one(
        "account.analytic.account", string="Cuenta analítica", tracking=True,
        domain="[('company_id', 'in', [False, company_id])]",
    )
    responsible_id = fields.Many2one("res.users", string="Responsable", tracking=True)
    notes = fields.Html(string="Notas")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("code_company_unique", "unique(code, company_id)",
         "El código del centro de costo debe ser único por empresa."),
    ]

    @api.constrains("hectares", "cost_type")
    def _check_hectares(self):
        for record in self:
            if record.hectares < 0:
                raise ValidationError("Las hectáreas no pueden ser negativas.")
