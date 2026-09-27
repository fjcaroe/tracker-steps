"""Puente D13 — el dato "verdadero" de fundo/especie/variedad/plantas vive
en `step_hr` cuando el centro está enlazado a una cuenta analítica real
(`step.management.cost.center.analytic_account_id`, ya opcional en el
núcleo). Nunca se sustituye el `Char`/`Float` del núcleo por completo (D13:
fallback portable); se agregan campos `agri_*` de sólo lectura que reflejan
el maestro real cuando la relación existe, y se dejan disponibles para que
`estimation.py` (este mismo puente) los use con procedencia explícita."""

from odoo import fields, models


class StepManagementCostCenter(models.Model):
    _inherit = "step.management.cost.center"

    agri_farm_id = fields.Many2one(
        related="analytic_account_id.fundo_id", string="Fundo (maestro agrícola)",
    )
    agri_species_id = fields.Many2one(
        related="analytic_account_id.especie_id", string="Especie (maestro agrícola)",
    )
    agri_variety_id = fields.Many2one(
        related="analytic_account_id.variedad_id", string="Variedad (maestro agrícola)",
    )
    agri_variety_group_id = fields.Many2one(
        related="analytic_account_id.grupo_variedad_id",
        string="Grupo de variedad (maestro agrícola)",
    )
    agri_plants = fields.Integer(
        related="analytic_account_id.plant_cost", string="Plantas (maestro agrícola)",
    )
    agri_hectares = fields.Integer(
        related="analytic_account_id.has_cost", string="Hectáreas (maestro agrícola)",
    )
