"""Puente D13 — el dato "verdadero" de fundo/especie/variedad/superficie y
plantas vive en `step_hr` (Actividades / Configuración / Centro de Costo).

Desde T51 el centro de costo de Gestión y Costos ES la cuenta analítica, de
modo que no hay un maestro paralelo que sincronizar: con `step_hr` instalado,
los campos de gestión de la cuenta (`farm`, `species`, `variety`, `hectares`,
`plants`, `cost_type`) se calculan desde sus datos agrícolas reales y quedan
editables (`readonly=False`) para los casos sin dato agrícola. Un valor ya
informado nunca se borra: si el maestro agrícola está vacío se conserva el
valor manual."""

from odoo import api, fields, models

COST_TYPE_BY_TYPE_COSTO = {
    "fruta": "crop",
    "cultivo": "crop",
    "maquinaria": "machinery",
    "operacional": "operational",
    "admin": "administrative",
}


class AccountAnalyticAccount(models.Model):
    _inherit = "account.analytic.account"

    # Native analytic accounts include activities outside agriculture. This
    # bridge loads after step_hr, preserving its master and selection values.
    fundo_id = fields.Many2one('step.fundo', required=False)
    type_costo = fields.Selection(required=False)
    etapa_costo = fields.Selection(required=False)
    tipo_fruta = fields.Selection(required=False)

    farm = fields.Char(compute="_compute_management_from_agriculture", store=True, readonly=False, precompute=True)
    species = fields.Char(compute="_compute_management_from_agriculture", store=True, readonly=False, precompute=True)
    variety = fields.Char(compute="_compute_management_from_agriculture", store=True, readonly=False, precompute=True)
    hectares = fields.Float(compute="_compute_management_from_agriculture", store=True, readonly=False, precompute=True)
    # A default on one field suppresses initial computation of the whole shared
    # compute group. Plants must come from plant_cost before the first insert.
    plants = fields.Float(compute="_compute_management_from_agriculture", store=True, readonly=False, precompute=True, default=None)
    cost_type = fields.Selection(compute="_compute_management_from_agriculture", store=True, readonly=False, precompute=True)

    @api.depends(
        "fundo_id.name", "especie_id.name", "variedad_id.name",
        "has_cost", "plant_cost", "type_costo",
    )
    def _compute_management_from_agriculture(self):
        for account in self:
            account.farm = account.fundo_id.name or account.farm
            account.species = account.especie_id.name or account.species
            account.variety = account.variedad_id.name or account.variety
            account.hectares = account.has_cost or account.hectares
            account.plants = float(account.plant_cost) if account.plant_cost else account.plants
            account.cost_type = (
                COST_TYPE_BY_TYPE_COSTO.get(account.type_costo) or account.cost_type
            )
