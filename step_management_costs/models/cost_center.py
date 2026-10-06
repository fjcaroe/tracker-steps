from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AccountAnalyticAccount(models.Model):
    """T51 — el centro de costo de Gestión y Costos ES la cuenta analítica.

    Se eliminó el maestro propio `step.management.cost.center`; todo el
    módulo apunta ahora a `account.analytic.account` (Actividades /
    Configuración / Centro de Costo). Los datos que las estimaciones,
    programas y presupuestos necesitan de un centro (superficie, plantas,
    ubicación productiva) viven como campos opcionales de la cuenta
    analítica. Con `step_hr` instalado, el puente agrícola los completa desde
    los maestros reales (fundo, especie, variedad, Has CCosto, Plantas CCosto).
    """

    _inherit = "account.analytic.account"

    cost_type = fields.Selection(
        [("crop", "Frutal / cultivo"), ("operational", "Operacional"),
         ("machinery", "Maquinaria"), ("administrative", "Administrativo"), ("other", "Otro")],
        string="Tipo (Gestión y Costos)", tracking=True,
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

    @api.constrains("hectares")
    def _check_hectares(self):
        for record in self:
            if record.hectares < 0:
                raise ValidationError("Las hectáreas no pueden ser negativas.")

    @api.constrains("plants")
    def _check_plants(self):
        for record in self:
            if record.plants < 0:
                raise ValidationError("El número de plantas no puede ser negativo.")
