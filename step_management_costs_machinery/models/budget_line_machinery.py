"""Corte V2 E — presupuesto de maquinaria sobre el detalle general existente.

`step.management.budget.line` ya tenía `category='machinery'` en el núcleo
(sin usar hasta ahora): este puente no inventa un documento paralelo, sólo
agrega la vinculación a la maquinaria real (vehículo + labor opcional) y el
cálculo de tarifa/desglose por componente sobre ese mismo detalle. El
presupuesto que lo contiene ya trae snapshot, revisión, aprobación,
multiempresa y moneda del núcleo (`operational_budget.py`) — nada de eso se
duplica aquí; sólo se extiende la protección de campos congelados con los
tres campos nuevos.
"""

import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.step_management_costs.models.operational_budget import (
    FROZEN_STATES, REVISION_LINE_FIELDS,
)

from .machinery_rate import get_effective_rate

MACHINERY_PROTECTED_FIELDS = {
    "machinery_vehicle_id", "machinery_labor_id", "machinery_component_json",
}

# Para que `_create_revision()` del núcleo no pierda estos campos al copiar
# la línea a una nueva revisión (ver `REVISION_LINE_FIELDS` en
# `operational_budget.py`).
REVISION_LINE_FIELDS.update(MACHINERY_PROTECTED_FIELDS)


class StepManagementBudgetLine(models.Model):
    _inherit = "step.management.budget.line"

    machinery_vehicle_id = fields.Many2one(
        "fleet.vehicle", string="Maquinaria", check_company=True, index=True,
        help="Sólo aplica a líneas de categoría «Maquinaria»: la máquina "
             "cuya tarifa estándar (o excepción por labor) alimenta la "
             "tarifa de la línea.",
    )
    machinery_labor_id = fields.Many2one(
        "step.labor", string="Labor (maquinaria)",
        help="Opcional. Si existe una tarifa específica para esta "
             "combinación de maquinaria y labor, reemplaza la tarifa "
             "estándar del vehículo.",
    )
    machinery_component_json = fields.Text(
        string="Desglose de componentes (JSON)", readonly=True, copy=False,
        help="Snapshot del desglose por concepto real (combustible, "
             "lubricantes, repuestos, mantenciones, arriendo, depreciación, "
             "mano de obra) tomado al calcular la tarifa.",
    )
    machinery_actual_hours = fields.Float(
        string="Horas reales (maquinaria)", compute="_compute_machinery_actual_hours",
        digits=(16, 2),
        help="Horas efectivas de `step.hrs.machinery.line` cuyo centro de "
             "costos y maquinaria coinciden con esta línea (relación "
             "demostrable). No incluye registros sin esa relación.",
    )

    @api.depends("category", "center_id", "machinery_vehicle_id")
    def _compute_machinery_actual_hours(self):
        Line = self.env["step.hrs.machinery.line"].sudo()
        for line in self:
            if line.category != "machinery" or not line.machinery_vehicle_id or not line.center_id.analytic_account_id:
                line.machinery_actual_hours = 0.0
                continue
            actual = Line.search([
                ("cost_id", "=", line.center_id.analytic_account_id.id),
                ("machinery_ids", "=", line.machinery_vehicle_id.id),
                ("state", "in", ("done", "costed", "accounted")),
            ])
            line.machinery_actual_hours = sum(actual.mapped("hrs_maquina"))

    def action_pull_machinery_rate(self):
        """Calcula la tarifa (hora/máquina) desde los conceptos reales del
        vehículo — o la excepción por labor si existe — y la aplica como
        `unit_price` de la línea. `quantity` (horas presupuestadas) no se
        toca: cero horas es válido y no es asunto de este botón."""
        for line in self:
            if line.category != "machinery":
                raise UserError(_(
                    "Sólo las líneas de categoría «Maquinaria» tienen tarifa de maquinaria."
                ))
            if not line.machinery_vehicle_id:
                raise UserError(_("Indique la maquinaria antes de calcular la tarifa."))
            if line.budget_id.state in FROZEN_STATES:
                raise UserError(_(
                    "El detalle del presupuesto %s está congelado. Cree una "
                    "nueva revisión."
                ) % line.budget_id.name)
            rate, components = get_effective_rate(
                self.env, line.machinery_vehicle_id, line.machinery_labor_id,
            )
            # La tarifa aplica uniforme a toda la distribución mensual de la
            # línea. `step.management.budget.month` valida su cuadratura
            # contra la línea padre apenas se escribe (`_check_parent_
            # distribution`, del núcleo) — actualizar la tarifa de un mes
            # existente con `(1, id, vals)` dispara esa validación *antes*
            # de que la línea misma tenga la tarifa nueva (el núcleo procesa
            # los comandos de `month_ids` antes que sus propios campos
            # simples dentro del mismo `write()`), y viceversa. La única
            # secuencia sin estado intermedio inconsistente es: (1) fijar la
            # tarifa con los meses vacíos —la validación se salta sin
            # meses—, (2) recrear los meses ya con la tarifa correcta en la
            # línea. No se toca el núcleo para esto.
            months = [(month.month, month.quantity) for month in line.month_ids]
            line.write({
                "unit_price": rate,
                "machinery_component_json": json.dumps(components, sort_keys=True),
                "month_ids": [(5, 0, 0)],
            })
            if months:
                line.write({
                    "month_ids": [
                        (0, 0, {"month": month, "quantity": quantity, "unit_price": rate})
                        for month, quantity in months
                    ],
                })
        return True

    def write(self, vals):
        touched = MACHINERY_PROTECTED_FIELDS & set(vals)
        if touched:
            frozen = self.filtered(lambda line: line.budget_id.state in FROZEN_STATES)
            if frozen:
                raise UserError(_(
                    "El detalle del presupuesto %s está congelado. Cree una "
                    "nueva revisión."
                ) % ", ".join(frozen.mapped("budget_id.name")))
        return super().write(vals)
