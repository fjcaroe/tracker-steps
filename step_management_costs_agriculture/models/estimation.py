"""Corte V2 D — completa la estimación con las fuentes reales de plantas y
rendimiento estándar cuando existen (D13, precedencia confirmada):
`step.rendimiento.line` (centro) → `step.variedad.line` (variedad) →
`step.grupo.variedad.line` (grupo de variedad). El método «Kilos» (D05)
nunca se ve afectado: sigue sin aplicar rendimiento. La procedencia elegida
se congela junto con el resto de la línea al validar (`PROTECTED_LINE_FIELDS`
del núcleo se extiende para incluirla).

El campo Actividad sigue bloqueado por D20: `product.template.actividad_id`
apunta hoy a `account.analytic.account`, no a `step.actividad`, y su
semántica real no está confirmada. Este puente no lo toca ni lo usa; el
maestro de rendimiento se busca por `labor_id` (M2o `product.template`)
directamente, un campo real y no ambiguo de `step.rendimiento.line`/
`step.variedad.line`/`step.grupo.variedad.line`.
"""

from odoo import _, api, fields, models

from odoo.addons.step_management_costs.models.estimation import PROTECTED_LINE_FIELDS

# Se congela junto con `plants`/`yield_ue`, ya protegidos por el núcleo.
PROTECTED_LINE_FIELDS.update({"plants_source", "yield_source"})


class StepManagementEstimation(models.Model):
    _inherit = "step.management.estimation"

    harvest_labor_id = fields.Many2one(
        "product.template", string="Labor de cosecha (maestro agrícola)",
        help="Labor/tarea usada para buscar el rendimiento estándar en los "
             "maestros agrícolas reales: centro → variedad → grupo de "
             "variedad. Vacía = se sigue usando sólo el rendimiento manual "
             "del núcleo (comportamiento sin este puente).",
    )

    def _agri_resolve_standard_yield(self, center):
        """(rendimiento, fuente) según la precedencia D13, o `(None, None)`
        si no hay labor elegida o ninguna fuente tiene una línea para ella."""
        self.ensure_one()
        account = center.analytic_account_id
        labor = self.harvest_labor_id
        if not account or not labor:
            return None, None

        line = self.env["step.rendimiento.line"].sudo().search([
            ("centro_id", "=", account.id), ("labor_id", "=", labor.id),
        ], limit=1)
        if line:
            return line.redim_std, _("Rendimiento del centro")

        variedad = account.variedad_id
        if variedad:
            vline = self.env["step.variedad.line"].sudo().search([
                ("variedad_id", "=", variedad.id), ("labor_id", "=", labor.id),
            ], limit=1)
            if vline:
                return float(vline.hec_rendimiento), _("Rendimiento de la variedad")

        grupo = account.grupo_variedad_id
        if grupo:
            gline = self.env["step.grupo.variedad.line"].sudo().search([
                ("grupo_variedad_id", "=", grupo.id), ("labor_id", "=", labor.id),
            ], limit=1)
            if gline:
                return float(gline.hec_rendimiento), _("Rendimiento del grupo de variedad")

        return None, None

    def action_compute_lines(self):
        res = super().action_compute_lines()
        for record in self:
            for line in record.line_ids:
                center = line.center_id
                account = center.analytic_account_id
                updates = {}

                if account and account.plant_cost:
                    updates["plants"] = float(account.plant_cost)
                    updates["plants_source"] = _("Maestro agrícola (centro)")
                else:
                    updates["plants_source"] = _("Núcleo (Char/Float propio)")

                yield_value, yield_source = record._agri_resolve_standard_yield(center)
                if yield_value is not None:
                    updates["yield_ue"] = yield_value
                    updates["yield_source"] = yield_source
                else:
                    updates["yield_source"] = _("Manual / por defecto (núcleo)")

                line.write(updates)
        return res


class StepManagementEstimationLine(models.Model):
    _inherit = "step.management.estimation.line"

    plants_source = fields.Char(
        string="Procedencia de plantas", readonly=True,
        help="De dónde se tomó `plants` al último recalcular. Se congela "
             "al validar, igual que el resto del detalle.",
    )
    yield_source = fields.Char(
        string="Procedencia del rendimiento", readonly=True,
        help="De dónde se tomó `yield_ue` al último recalcular: centro, "
             "variedad, grupo de variedad, o manual/por defecto si ninguna "
             "fuente real tenía una línea para la labor elegida.",
    )
