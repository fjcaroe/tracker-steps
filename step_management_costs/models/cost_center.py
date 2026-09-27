from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class StepManagementCostCenter(models.Model):
    _name = "step.management.cost.center"
    _description = "Centro de costo operativo"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "code, name"
    _check_company_auto = True

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
    plants = fields.Float(
        string="Plantas", digits=(16, 2), default=0.0, tracking=True,
        help="Número de plantas del centro/cuartel. Lo usan las estimaciones "
             "de cosecha con el método «Plantas». Valor inicial 0; no altera "
             "datos heredados.",
    )
    farm = fields.Char(string="Fundo", tracking=True)
    plot = fields.Char(string="Cuartel", tracking=True)
    species = fields.Char(string="Especie", tracking=True)
    variety = fields.Char(string="Variedad", tracking=True)
    analytic_account_id = fields.Many2one(
        "account.analytic.account", string="Cuenta analítica", tracking=True,
        check_company=True,
        domain="[('company_id', 'in', [False, company_id])]",
        help="Cuenta analítica de la misma empresa. Obligatoria para aprobar "
             "nuevos presupuestos que incluyan este centro (no es obligatoria "
             "para instalar ni para actualizar datos heredados).",
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

    @api.constrains("plants")
    def _check_plants(self):
        for record in self:
            if record.plants < 0:
                raise ValidationError("El número de plantas no puede ser negativo.")

    def account_to_center_map(self):
        """Diccionario `cuenta analítica.id → centro`, exigiendo que sea
        1 a 1. Dos centros pueden compartir intencionalmente una cuenta
        analítica en otros contextos (p. ej. mientras se completa el
        maestro), pero cualquier lectura que atribuya un apunte contable
        real a "el" centro de una cuenta —como esta— necesita esa relación
        inequívoca; si no, un apunte terminaría asignado al centro que
        gane la colisión en vez de reportarse como ambiguo. Mismo criterio
        que `operational.budget._duplicate_analytic_centers()`, generalizado
        a cualquier conjunto de centros (no sólo los de un presupuesto)."""
        by_account = {}
        for center in self.filtered("analytic_account_id"):
            by_account.setdefault(center.analytic_account_id.id, self.browse())
            by_account[center.analytic_account_id.id] |= center
        duplicates = {
            account_id: centers for account_id, centers in by_account.items()
            if len(centers) > 1
        }
        if duplicates:
            raise UserError(_(
                "No es posible atribuir el gasto real a un centro: varios "
                "centros comparten la misma cuenta analítica: %s"
            ) % "; ".join(
                ", ".join(centers.mapped("display_name")) for centers in duplicates.values()
            ))
        return {account_id: centers[0] for account_id, centers in by_account.items()}
