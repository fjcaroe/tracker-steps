"""Puente D13 â€” el dato "verdadero" de fundo/especie/variedad/plantas vive
en `step_hr` cuando el centro estÃ¡ enlazado a una cuenta analÃ­tica real
(`step.management.cost.center.analytic_account_id`, ya opcional en el
nÃºcleo). Nunca se sustituye el `Char`/`Float` del nÃºcleo por completo (D13:
fallback portable); se agregan campos `agri_*` de sÃ³lo lectura que reflejan
el maestro real cuando la relaciÃ³n existe, y se dejan disponibles para que
`estimation.py` (este mismo puente) los use con procedencia explÃ­cita."""

from odoo import fields, models


class StepManagementCostCenter(models.Model):
    _inherit = "step.management.cost.center"

    agri_farm_id = fields.Many2one(
        related="analytic_account_id.fundo_id", string="Fundo (maestro agrÃ­cola)",
    )
    agri_species_id = fields.Many2one(
        related="analytic_account_id.especie_id", string="Especie (maestro agrÃ­cola)",
    )
    agri_variety_id = fields.Many2one(
        related="analytic_account_id.variedad_id", string="Variedad (maestro agrÃ­cola)",
    )
    agri_variety_group_id = fields.Many2one(
        related="analytic_account_id.grupo_variedad_id",
        string="Grupo de variedad (maestro agrÃ­cola)",
    )
    agri_plants = fields.Integer(
        related="analytic_account_id.plant_cost", string="Plantas (maestro agrÃ­cola)",
    )
    agri_hectares = fields.Float(digits=(16, 2),
        related="analytic_account_id.has_cost", string="HectÃ¡reas (maestro agrÃ­cola)",
    )
