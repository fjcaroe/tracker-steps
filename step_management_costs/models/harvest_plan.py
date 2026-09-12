"""Plan de cosecha y recursos derivado de una estimación validada (Fase 4;
reescrito en Corte V2 A).

`Anexo 1.6.9 plan de cosecha V2.xlsx` (hechos verificados por el cliente)
demuestra que el reparto semanal de kilos es **por centro de costo**, no una
sola foto agregada: cada línea de la estimación (`estimation.line`, ya por
centro) aporta su propio `total_kg`, que se reparte entre las semanas con el
**mismo porcentaje de la curva semanal validada** de la estimación
(`estimation.week_curve_id`). El residuo de redondeo se asigna a la última
semana **de cada centro**, para que tanto cada centro como el total general
concilien exactamente con `estimation.total_kg`.

No se modifica `estimation.py`: `estimation.distribution_ids` (eje semana)
sigue siendo el agregado de toda la estimación (compatible con lo ya
validado); este archivo recalcula el reparto centro×semana de forma
independiente, a partir de datos que ya existen y son inmutables una vez la
estimación fue validada.

Compatibilidad: `harvest.plan.line.center_id` es **nuevo y opcional** — los
planes confirmados antes de este corte no lo tienen y no se les asigna nada
automáticamente (no hay fuente que lo demuestre). Sólo los planes generados
o revisados desde este corte en adelante llevan centro por línea.

Un plan confirmado es inmutable (snapshot + hash, mismo patrón que
`crop_program.py`/`estimation.py`); la corrección es una nueva revisión.
"""

import hashlib
import json
import math

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_round

from .estimation import KG_PRECISION_NAME

APPROVER_GROUP = "step_management_costs.group_management_approver"
MANAGER_GROUP = "step_management_costs.group_management_manager"

FROZEN_STATES = ("confirmed", "superseded")

PROTECTED_HEADER_FIELDS = {
    "company_id", "estimation_id", "container_unit_id",
    "round_up_containers", "line_ids",
}


class StepManagementHarvestPlan(models.Model):
    _name = "step.management.harvest.plan"
    _description = "Plan de cosecha semanal"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        string="Folio", required=True, copy=False, readonly=True,
        default=lambda self: _("Nuevo"), index=True,
    )
    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True,
        default=lambda self: self.env.company, index=True, tracking=True,
    )
    date = fields.Date(
        string="Fecha", required=True, default=fields.Date.context_today, tracking=True,
    )
    estimation_id = fields.Many2one(
        "step.management.estimation", string="Estimación", required=True,
        check_company=True, tracking=True,
        domain="[('company_id', '=', company_id), ('state', '=', 'validated')]",
    )
    season = fields.Char(string="Temporada", readonly=True)
    container_unit_id = fields.Many2one(
        "step.management.estimation.unit", string="Envase (unidad)",
        check_company=True, domain="[('company_id', '=', company_id)]",
        help="Unidad usada para contar envases por semana. Por defecto, la "
             "unidad de la estimación.",
    )
    round_up_containers = fields.Boolean(
        string="Redondear envases hacia arriba", default=True,
        help="D08: recursos indivisibles al alza. Desmárquelo para dejar la "
             "división exacta.",
    )
    line_ids = fields.One2many(
        "step.management.harvest.plan.line", "harvest_plan_id", string="Centro / semana",
        copy=False,
    )
    resource_ids = fields.One2many(
        "step.management.harvest.resource", "harvest_plan_id", string="Recursos",
        copy=True,
    )
    total_kg = fields.Float(
        string="Total kg", compute="_compute_totals", store=True, digits=KG_PRECISION_NAME,
    )
    total_containers = fields.Float(
        string="Total envases", compute="_compute_totals", store=True, digits=(16, 2),
    )
    center_count = fields.Integer(compute="_compute_totals", store=True)

    state = fields.Selection(
        [("draft", "Borrador"), ("confirmed", "Confirmado"),
         ("superseded", "Reemplazado")],
        string="Estado", default="draft", required=True, index=True, tracking=True,
    )
    revision = fields.Integer(string="Revisión", default=1, copy=False, tracking=True)
    revision_of_id = fields.Many2one(
        "step.management.harvest.plan", string="Revisión de", copy=False,
        ondelete="set null", readonly=True,
    )
    superseded_by_id = fields.Many2one(
        "step.management.harvest.plan", string="Reemplazado por", copy=False,
        ondelete="set null", readonly=True,
    )
    reopen_reason = fields.Text(string="Motivo de la revisión", copy=False, readonly=True)
    confirmed_by_id = fields.Many2one(
        "res.users", string="Confirmado por", readonly=True, copy=False,
    )
    confirmed_at = fields.Datetime(string="Fecha de confirmación", readonly=True, copy=False)
    confirmation_snapshot = fields.Text(
        string="Snapshot de confirmación", copy=False, readonly=True,
        help="Copia congelada (JSON) del detalle centro/semana y de los "
             "recursos al confirmar.",
    )
    confirmation_hash = fields.Char(
        string="Hash del snapshot", size=64, copy=False, readonly=True,
    )
    notes = fields.Html(string="Notas")
    active = fields.Boolean(default=True)

    @api.depends("line_ids.kg", "line_ids.containers", "line_ids.center_id")
    def _compute_totals(self):
        for record in self:
            record.total_kg = sum(record.line_ids.mapped("kg"))
            record.total_containers = sum(record.line_ids.mapped("containers"))
            record.center_count = len(record.line_ids.mapped("center_id"))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "step.management.harvest.plan"
                ) or _("Nuevo")
        return super().create(vals_list)

    def _kg_rounding(self):
        digits = self.env["decimal.precision"].precision_get(KG_PRECISION_NAME)
        return 10 ** (-(digits or 2))

    def _ensure_approver(self):
        if not self.env.user.has_group(APPROVER_GROUP):
            raise UserError(_(
                "Necesita el perfil «Aprobador / Control» de Gestión y "
                "Costos para esta acción."
            ))

    # ------------------------------------------------------------------
    # Generación centro × semana (V2 A)
    # ------------------------------------------------------------------
    def action_generate(self):
        for record in self:
            if record.state != "draft":
                raise UserError(_(
                    "Sólo se puede regenerar un plan de cosecha en borrador."
                ))
            estimation = record.estimation_id
            if not estimation or estimation.state != "validated":
                raise UserError(_(
                    "El plan de cosecha requiere una estimación validada."
                ))
            if estimation.company_id != record.company_id:
                raise UserError(_("La estimación pertenece a otra empresa."))
            week_curve = estimation.week_curve_id
            if not week_curve:
                raise UserError(_(
                    "La estimación no tiene curva semanal validada."
                ))
            curve_lines = week_curve.line_ids.sorted(key=lambda cl: (cl.sequence, cl.id))
            if not curve_lines:
                raise UserError(_("La curva semanal no tiene líneas."))
            if not estimation.line_ids:
                raise UserError(_(
                    "La estimación no tiene detalle por centro de costo."
                ))

            unit = record.container_unit_id or estimation.unit_id
            kg_factor = unit.kg_factor or 1.0
            rounding = record._kg_rounding()
            count = len(curve_lines)

            commands = [(5, 0, 0)]
            for line in estimation.line_ids:
                center_total = float_round(line.total_kg, precision_rounding=rounding)
                running = 0.0
                for index, curve_line in enumerate(curve_lines):
                    if index < count - 1:
                        kg = float_round(
                            center_total * curve_line.percentage / 100.0,
                            precision_rounding=rounding,
                        )
                        running = float_round(running + kg, precision_rounding=rounding)
                    else:
                        # residuo del centro a su última semana (D08/D04)
                        kg = float_round(center_total - running, precision_rounding=rounding)
                    exact = kg / kg_factor if kg_factor else 0.0
                    containers = math.ceil(exact) if record.round_up_containers else exact
                    commands.append((0, 0, {
                        "center_id": line.center_id.id,
                        "species": line.species or estimation.species,
                        "variety": line.variety or estimation.variety,
                        "week_number": curve_line.week_number,
                        "week_label": curve_line.dimension_name or ("W%02d" % curve_line.week_number),
                        "kg": kg,
                        "containers": containers,
                    }))

            record.write({
                "line_ids": commands,
                "season": estimation.season,
                "container_unit_id": unit.id,
            })
            if float_compare(
                record.total_kg, estimation.total_kg, precision_rounding=rounding
            ) != 0:
                raise UserError(_(
                    "El plan suma %(got).4f kg y no concilia con la estimación "
                    "(%(exp).4f kg)."
                ) % {"got": record.total_kg, "exp": estimation.total_kg})
            for center in estimation.line_ids.mapped("center_id"):
                center_lines = record.line_ids.filtered(lambda l, c=center: l.center_id == c)
                center_expected = estimation.line_ids.filtered(
                    lambda l, c=center: l.center_id == c
                ).total_kg
                center_got = float_round(
                    sum(center_lines.mapped("kg")), precision_rounding=rounding,
                )
                if float_compare(center_got, center_expected, precision_rounding=rounding) != 0:
                    raise UserError(_(
                        "El centro %(center)s suma %(got).4f kg y no concilia "
                        "con su estimación (%(exp).4f kg)."
                    ) % {"center": center.display_name, "got": center_got, "exp": center_expected})
            record.resource_ids._compute_weeks()
            record.message_post(body=_(
                "Plan de cosecha generado desde %(est)s: %(centers)s centro(s), "
                "%(weeks)s semana(s) por centro, %(kg).2f kg."
            ) % {"est": estimation.name, "centers": len(estimation.line_ids),
                 "weeks": count, "kg": record.total_kg})
        return True

    def _build_confirmation_snapshot(self):
        self.ensure_one()
        lines = []
        for line in self.line_ids.sorted(key=lambda l: (l.center_id.id, l.week_number, l.id)):
            lines.append({
                "center": line.center_id.code or line.center_id.display_name,
                "species": line.species or "",
                "variety": line.variety or "",
                "week_number": line.week_number,
                "week_label": line.week_label or "",
                "kg": round(line.kg, 4),
                "containers": round(line.containers, 2),
            })
        resources = []
        for resource in self.resource_ids.sorted(key=lambda r: (r.sequence, r.id)):
            resources.append({
                "resource_key": resource.resource_key,
                "label": resource.label,
                "factor": round(resource.factor, 6),
                "weeks": [
                    {"week_number": w.week_number, "value": round(w.value, 4)}
                    for w in resource.week_ids.sorted(key=lambda w: w.week_number)
                ],
            })
        payload = {
            "plan": self.name,
            "revision": self.revision,
            "company": self.company_id.name,
            "estimation": self.estimation_id.name,
            "season": self.season,
            "total_kg": round(self.total_kg, 4),
            "total_containers": round(self.total_containers, 2),
            "lines": lines,
            "resources": resources,
        }
        return json.dumps(payload, sort_keys=True, ensure_ascii=False)

    def action_confirm(self):
        for record in self:
            if record.state != "draft":
                raise UserError(_("El plan ya está confirmado."))
            if not record.line_ids:
                raise UserError(_("Genere el plan antes de confirmarlo."))
            snapshot = record._build_confirmation_snapshot()
            record.write({
                "state": "confirmed",
                "confirmed_by_id": self.env.user.id,
                "confirmed_at": fields.Datetime.now(),
                "confirmation_snapshot": snapshot,
                "confirmation_hash": hashlib.sha256(snapshot.encode("utf-8")).hexdigest(),
            })
            origin = record.revision_of_id
            if origin and origin.state == "confirmed":
                origin.write({"state": "superseded", "superseded_by_id": record.id})
                origin.message_post(body=_(
                    "Reemplazado por la revisión %(rev)s (%(name)s)."
                ) % {"rev": record.revision, "name": record.name})

    def action_reset_to_draft(self):
        if not self.env.user.has_group(APPROVER_GROUP):
            raise UserError(_(
                "Sólo un aprobador puede reabrir un plan de cosecha confirmado."
            ))
        self.filtered(lambda r: r.state == "confirmed").write({"state": "draft"})

    def _create_revision(self, reason=None):
        self.ensure_one()
        self._ensure_approver()
        if self.state != "confirmed":
            raise UserError(_(
                "Sólo un plan de cosecha confirmado puede revisarse."
            ))
        existing = self.search([
            ("revision_of_id", "=", self.id), ("state", "!=", "superseded"),
        ], limit=1)
        if existing:
            raise UserError(_(
                "Ya existe la revisión %(name)s en estado %(state)s."
            ) % {"name": existing.display_name, "state": existing.state})
        children = self.search([("revision_of_id", "=", self.id)])
        next_revision = max(children.mapped("revision") or [self.revision]) + 1
        revision = self.copy({
            "revision": next_revision, "revision_of_id": self.id,
            "reopen_reason": (reason or "").strip() or False,
        })
        self.message_post(body=_(
            "Se creó la revisión %(rev)s (%(name)s). Este plan permanece "
            "inmutable y vigente hasta que la revisión sea confirmada."
        ) % {"rev": revision.revision, "name": revision.name})
        return revision

    def _do_reopen(self, reason):
        self.ensure_one()
        if not reason or not reason.strip():
            raise UserError(_("Debe indicar el motivo de la corrección."))
        return self._create_revision(reason=reason)

    def action_new_revision(self):
        revision = self._create_revision()
        return {
            "type": "ir.actions.act_window",
            "res_model": "step.management.harvest.plan",
            "res_id": revision.id, "view_mode": "form", "target": "current",
        }

    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {})
        default.setdefault("name", _("Nuevo"))
        default.setdefault("state", "draft")
        default.update({
            "confirmed_by_id": False, "confirmed_at": False,
            "confirmation_snapshot": False, "confirmation_hash": False,
            "superseded_by_id": False,
        })
        return super().copy(default)

    def write(self, vals):
        touched = PROTECTED_HEADER_FIELDS & set(vals)
        if touched:
            frozen = self.filtered(lambda r: r.state in FROZEN_STATES)
            if frozen:
                raise UserError(_(
                    "El plan de cosecha %(names)s está confirmado/reemplazado "
                    "y no admite cambios en: %(fields)s. Cree una nueva "
                    "revisión."
                ) % {
                    "names": ", ".join(frozen.mapped("name")),
                    "fields": ", ".join(sorted(touched)),
                })
        return super().write(vals)

    def unlink(self):
        blocked = self.filtered(lambda r: r.state in FROZEN_STATES)
        if blocked and not self.env.user.has_group(MANAGER_GROUP):
            raise UserError(_(
                "Sólo un administrador puede eliminar planes de cosecha "
                "confirmados/reemplazados: %s"
            ) % ", ".join(blocked.mapped("name")))
        if blocked:
            raise UserError(_(
                "No se puede eliminar un plan de cosecha confirmado/"
                "reemplazado (%s)."
            ) % ", ".join(blocked.mapped("name")))
        return super().unlink()


class StepManagementHarvestPlanLine(models.Model):
    _name = "step.management.harvest.plan.line"
    _description = "Semana del plan de cosecha por centro"
    _order = "harvest_plan_id, center_id, week_number, id"
    _check_company_auto = True

    harvest_plan_id = fields.Many2one(
        "step.management.harvest.plan", string="Plan", required=True,
        ondelete="cascade", check_company=True, index=True,
    )
    company_id = fields.Many2one(
        related="harvest_plan_id.company_id", string="Empresa", store=True, index=True,
    )
    center_id = fields.Many2one(
        "step.management.cost.center", string="Centro de costo", check_company=True,
        index=True,
        help="Nuevo en V2 A. Vacío en planes generados antes de este corte "
             "(no se asigna retroactivamente sin una fuente que lo demuestre).",
    )
    species = fields.Char(string="Especie")
    variety = fields.Char(string="Variedad")
    week_number = fields.Integer(string="Semana")
    week_label = fields.Char(string="Semana")
    kg = fields.Float(string="Kilos", digits=KG_PRECISION_NAME)
    containers = fields.Float(string="Envases", digits=(16, 2))
    notes = fields.Char(string="Observación")

    _sql_constraints = [
        ("harvest_plan_line_center_week_unique",
         "unique(harvest_plan_id, center_id, week_number)",
         "No puede repetirse el mismo centro y semana en un plan de cosecha "
         "(Postgres no aplica esto a filas heredadas sin centro)."),
    ]

    def _assert_parent_editable(self):
        frozen = self.filtered(
            lambda line: line.harvest_plan_id.state in FROZEN_STATES
        )
        if frozen:
            raise UserError(_(
                "El plan de cosecha está confirmado/reemplazado y es inmutable."
            ))

    @api.model_create_multi
    def create(self, vals_list):
        plans = self.env["step.management.harvest.plan"].browse([
            vals.get("harvest_plan_id") for vals in vals_list if vals.get("harvest_plan_id")
        ])
        if any(plan.state in FROZEN_STATES for plan in plans):
            raise UserError(_(
                "El plan de cosecha confirmado/reemplazado es inmutable."
            ))
        return super().create(vals_list)

    def write(self, vals):
        self._assert_parent_editable()
        return super().write(vals)

    def unlink(self):
        self._assert_parent_editable()
        return super().unlink()
