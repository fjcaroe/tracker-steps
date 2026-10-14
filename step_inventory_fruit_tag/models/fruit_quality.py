from odoo import fields, models


class StepManagementFruitQuality(models.Model):
    """Grado de calidad de fruta (ej. A, B, C1), símil de category/class/caliber
    ya existentes en step_management_costs (estimation_curve.py) para el
    mismo propósito de clasificación de fruta."""

    _name = "step.management.fruit.quality"
    _description = "Calidad de fruta"
    _order = "sequence, code, name"
    _check_company_auto = True

    name = fields.Char(string="Nombre", required=True)
    code = fields.Char(string="Código", required=True, index=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True,
        default=lambda self: self.env.company, index=True,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("fruit_quality_code_company_unique", "unique(code, company_id)",
         "El código de la calidad debe ser único por empresa."),
    ]
