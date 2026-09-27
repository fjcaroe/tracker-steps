"""Corte V2 F, puntos 1-2 y 7 — comparativo de temporada vs. temporada
anterior.

Fuente única: `step.management.historical.cost` — el hecho normalizado ya
construido en el Corte V2 B (una fila = un hecho de una fuente, «Presupuesto
histórico» o «Real histórico», o un registro manual pareado heredado). No se
mezclan fuentes «vivas» (contabilidad analítica) con el histórico normalizado
en esta misma comparación — evita el doble conteo explícitamente pedido por
el corte. Los registros «sin clasificar» (`origin == 'unreviewed'`) se
excluyen, igual que ya hace el propio modelo para sus comparativos.

Variación %: siempre se calcula desde los totales ya sumados (temporada
actual vs. anterior), nunca sumando ni promediando porcentajes de fila —
punto explícito del corte.
"""

import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

DIMENSIONS = [
    ("farm", "Fundo"), ("species", "Especie"), ("variety", "Variedad"),
    ("center", "Centro de costo"), ("origin", "Origen"),
    ("budget_group", "Grupo presupuestario"), ("activity", "Actividad"),
    ("product", "Producto-labor"),
]
METRICS = [("actual", "Real"), ("budget", "Presupuesto")]
UNCLASSIFIED = _("Sin clasificar")

_SEASON_RE = re.compile(r"^(\d{4})/(\d{4})$")


def shift_season(season, delta=-1):
    """«2026/2027» con `delta=-1` → «2025/2026». `None` si `season` no sigue
    el formato «20AA/20BB» normalizado (mismo formato que ya produce
    `_season_code_to_string`; no es un maestro, D03/K1 siguen abiertas)."""
    match = _SEASON_RE.match((season or "").strip())
    if not match:
        return None
    first, second = int(match.group(1)), int(match.group(2))
    return "%d/%d" % (first + delta, second + delta)


class StepManagementSeasonComparisonWizard(models.TransientModel):
    _name = "step.management.season.comparison.wizard"
    _description = "Comparativo de temporada vs. temporada anterior"

    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True, default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(related="company_id.currency_id")
    season = fields.Char(string="Temporada", required=True)
    previous_season = fields.Char(string="Temporada anterior", required=True)
    dimension = fields.Selection(DIMENSIONS, string="Dimensión", required=True, default="center")
    metric = fields.Selection(METRICS, string="Métrica", required=True, default="actual")
    computed = fields.Boolean(default=False)
    line_ids = fields.One2many(
        "step.management.season.comparison.line", "wizard_id", string="Detalle",
    )
    total_current_amount = fields.Monetary(compute="_compute_totals", currency_field="currency_id")
    total_previous_amount = fields.Monetary(compute="_compute_totals", currency_field="currency_id")
    total_current_amount_usd = fields.Float(compute="_compute_totals", digits=(16, 2))
    total_previous_amount_usd = fields.Float(compute="_compute_totals", digits=(16, 2))
    total_variance_amount = fields.Monetary(compute="_compute_totals", currency_field="currency_id")
    total_variance_percent = fields.Float(compute="_compute_totals")
    total_variance_percent_available = fields.Boolean(compute="_compute_totals")

    @api.onchange("season")
    def _onchange_season_suggest_previous(self):
        if self.season and not self.previous_season:
            self.previous_season = shift_season(self.season)

    @api.depends(
        "line_ids.current_amount", "line_ids.previous_amount",
        "line_ids.current_amount_usd", "line_ids.previous_amount_usd",
    )
    def _compute_totals(self):
        for wiz in self:
            current = sum(wiz.line_ids.mapped("current_amount"))
            previous = sum(wiz.line_ids.mapped("previous_amount"))
            wiz.total_current_amount = current
            wiz.total_previous_amount = previous
            wiz.total_current_amount_usd = sum(wiz.line_ids.mapped("current_amount_usd"))
            wiz.total_previous_amount_usd = sum(wiz.line_ids.mapped("previous_amount_usd"))
            wiz.total_variance_amount = current - previous
            wiz.total_variance_percent_available = bool(previous)
            wiz.total_variance_percent = (
                (current - previous) * 100.0 / previous if previous else 0.0
            )

    def _dimension_value(self, record):
        if self.dimension == "center":
            value = record.center_label or record.center_id.display_name
        elif self.dimension == "budget_group":
            value = record.budget_group_label or record.group_id.display_name
        else:
            value = getattr(record, "%s_label" % self.dimension, None)
            if value is None:  # farm / species / variety: campo directo, sin sufijo
                value = getattr(record, self.dimension, None)
        value = (value or "").strip() if isinstance(value, str) else value
        return value or UNCLASSIFIED

    def _fetch_buckets(self, season):
        self.ensure_one()
        Cost = self.env["step.management.historical.cost"].sudo()
        records = Cost.search([
            ("company_id", "=", self.company_id.id),
            ("season", "=", season),
            ("origin", "!=", "unreviewed"),
        ])
        buckets = {}
        for record in records:
            key = self._dimension_value(record)
            amount = record.budget_amount if self.metric == "budget" else record.actual_amount
            amount_usd = (
                record.source_amount_usd if record.dataset_kind
                else (record.budget_amount_converted if self.metric == "budget"
                      else record.actual_amount_converted)
            )
            bucket = buckets.setdefault(key, {"amount": 0.0, "amount_usd": 0.0})
            bucket["amount"] += amount
            bucket["amount_usd"] += amount_usd
        return buckets

    def action_compute(self):
        self.ensure_one()
        if self.season == self.previous_season:
            raise ValidationError(_(
                "La temporada y la temporada anterior deben ser distintas."
            ))
        self.line_ids.unlink()
        current = self._fetch_buckets(self.season)
        previous = self._fetch_buckets(self.previous_season)
        commands = []
        for key in sorted(set(current) | set(previous)):
            cur = current.get(key, {"amount": 0.0, "amount_usd": 0.0})
            prev = previous.get(key, {"amount": 0.0, "amount_usd": 0.0})
            variance = cur["amount"] - prev["amount"]
            commands.append((0, 0, {
                "dimension_value": key,
                "current_amount": cur["amount"], "previous_amount": prev["amount"],
                "current_amount_usd": cur["amount_usd"], "previous_amount_usd": prev["amount_usd"],
                "variance_amount": variance,
                "variance_percent": (variance * 100.0 / prev["amount"]) if prev["amount"] else 0.0,
                "variance_percent_available": bool(prev["amount"]),
            }))
        self.write({"line_ids": commands, "computed": True})
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name, "res_id": self.id,
            "view_mode": "form", "target": "new",
        }


class StepManagementSeasonComparisonLine(models.TransientModel):
    _name = "step.management.season.comparison.line"
    _description = "Línea del comparativo de temporada"
    _order = "current_amount desc, id"

    wizard_id = fields.Many2one(
        "step.management.season.comparison.wizard", required=True, ondelete="cascade",
    )
    currency_id = fields.Many2one(related="wizard_id.currency_id")
    dimension_value = fields.Char(string="Valor")
    current_amount = fields.Monetary(string="Temporada actual", currency_field="currency_id")
    previous_amount = fields.Monetary(string="Temporada anterior", currency_field="currency_id")
    current_amount_usd = fields.Float(string="Actual US$", digits=(16, 2))
    previous_amount_usd = fields.Float(string="Anterior US$", digits=(16, 2))
    variance_amount = fields.Monetary(string="Var $", currency_field="currency_id")
    variance_percent = fields.Float(string="Var %")
    variance_percent_available = fields.Boolean(
        string="Var % disponible",
        help="Falso cuando la temporada anterior no tiene monto — no hay "
             "base de comparación (no es lo mismo que «0 % de variación»).",
    )
