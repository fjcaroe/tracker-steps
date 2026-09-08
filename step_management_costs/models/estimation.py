"""Fase 3, corte 2 — Documento de estimación de cosecha por centro/cuartel.

Construye la estimación a partir de los maestros y de las curvas validadas del
corte 1 (`estimation_curve.py`). Aplica la fórmula D05 (`DECISION_LOG.md`):

- plantas:   total_ue = plantas   * rendimiento_ue
- hectáreas: total_ue = hectáreas * rendimiento_ue
- kilos:     el usuario ingresa total_kg directamente
- para plantas/hectáreas: total_kg = total_ue * unidad.kg_factor
- nunca se multiplica dos veces por rendimiento_ue.

Al validar (rol aprobador) se generan líneas normalizadas de distribución por
semana, grupo de calibre y clase de fruta. Cada eje concilia exactamente con
total_kg: cada porción se redondea a la precisión de peso y el residuo se
asigna a la última línea ordenada. La generación es determinista, idempotente
y transaccional; una estimación validada y sus distribuciones son inmutables y
sólo se corrigen creando una revisión (sin bypass por contexto RPC).
"""

import hashlib
import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_round

APPROVER_GROUP = "step_management_costs.group_management_approver"
MANAGER_GROUP = "step_management_costs.group_management_manager"

KG_PRECISION_NAME = "Estimación de cosecha"

METHOD_SELECTION = [
    ("plants", "Plantas"),
    ("hectares", "Hectáreas"),
    ("kilos", "Kilos"),
]
AXIS_SELECTION = [
    ("week", "Semana"),
    ("caliber", "Grupo de calibre"),
    ("class", "Clase de fruta"),
]
# Curva esperada por eje.
AXIS_CURVE_TYPE = {"week": "week", "caliber": "caliber", "class": "class"}

FROZEN_STATES = ("validated", "superseded")

# Campos de cabecera que quedan congelados en una estimación validada/reemplazada.
PROTECTED_HEADER_FIELDS = {
    "company_id", "version_id", "season", "species", "variety", "unit_id",
    "method", "default_yield_ue", "week_curve_id", "caliber_curve_id",
    "class_curve_id", "center_ids", "line_ids", "distribution_ids",
}
# Campos de detalle que reproducen el cálculo: congelados tras validar.
PROTECTED_LINE_FIELDS = {
    "center_id", "farm", "plot", "species", "variety", "hectares", "plants",
    "yield_ue", "kg_factor", "total_kg_input",
}


class StepManagementEstimationVersion(models.Model):
    _name = "step.management.estimation.version"
    _description = "Versión de estimación de cosecha"
    _order = "season desc, code, name"
    _check_company_auto = True

    code = fields.Char(string="Código", required=True, index=True)
    name = fields.Char(string="Nombre", required=True)
    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True,
        default=lambda self: self.env.company, index=True,
    )
    season = fields.Char(string="Temporada", required=True, help="Ej.: 2026/2027")
    deadline_date = fields.Date(string="Fecha límite")
    state = fields.Selection(
        [("draft", "Borrador"), ("open", "Abierta"), ("closed", "Cerrada")],
        string="Estado", default="draft", required=True, index=True,
    )
    notes = fields.Html(string="Notas")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("estimation_version_code_company_unique", "unique(code, company_id)",
         "El código de la versión de estimación debe ser único por empresa."),
    ]

    def action_open(self):
        self.write({"state": "open"})

    def action_close(self):
        self.write({"state": "closed"})

    def action_set_draft(self):
        self.write({"state": "draft"})


class StepManagementEstimation(models.Model):
    _name = "step.management.estimation"
    _description = "Documento de estimación de cosecha"
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
    version_id = fields.Many2one(
        "step.management.estimation.version", string="Versión", required=True,
        check_company=True, tracking=True,
        domain="[('company_id', '=', company_id)]",
    )
    season = fields.Char(string="Temporada", required=True, tracking=True, help="Ej.: 2026/2027")
    species = fields.Char(string="Especie", tracking=True)
    variety = fields.Char(string="Variedad", tracking=True)
    unit_id = fields.Many2one(
        "step.management.estimation.unit", string="Unidad de estimación",
        required=True, check_company=True, tracking=True,
        domain="[('company_id', '=', company_id)]",
    )
    method = fields.Selection(
        METHOD_SELECTION, string="Método de cálculo", required=True,
        default="plants", tracking=True,
        help="Plantas / Hectáreas: total_ue = base * rendimiento_ue y "
             "total_kg = total_ue * factor kg. Kilos: total_kg se ingresa "
             "directamente y no se aplica otra multiplicación.",
    )
    default_yield_ue = fields.Float(
        string="Rendimiento por defecto (UE)", digits=(16, 6),
        help="Rendimiento en unidades de estimación por planta o por hectárea. "
             "Se copia a cada línea nueva; puede ajustarse por cuartel.",
    )
    week_curve_id = fields.Many2one(
        "step.management.estimation.curve", string="Curva semanal",
        check_company=True,
        domain="[('company_id', '=', company_id), ('curve_type', '=', 'week'), "
               "('state', '=', 'validated'), ('active', '=', True)]",
    )
    caliber_curve_id = fields.Many2one(
        "step.management.estimation.curve", string="Curva de grupos de calibre",
        check_company=True,
        domain="[('company_id', '=', company_id), ('curve_type', '=', 'caliber'), "
               "('state', '=', 'validated'), ('active', '=', True)]",
    )
    class_curve_id = fields.Many2one(
        "step.management.estimation.curve", string="Curva de clases de fruta",
        check_company=True,
        domain="[('company_id', '=', company_id), ('curve_type', '=', 'class'), "
               "('state', '=', 'validated'), ('active', '=', True)]",
    )
    center_ids = fields.Many2many(
        "step.management.cost.center", "step_management_estimation_center_rel",
        "estimation_id", "center_id", string="Centros de costo / cuarteles",
        domain="[('company_id', '=', company_id)]",
    )
    line_ids = fields.One2many(
        "step.management.estimation.line", "estimation_id", string="Detalle", copy=True,
    )
    distribution_ids = fields.One2many(
        "step.management.estimation.distribution", "estimation_id",
        string="Distribución normalizada", copy=False,
    )

    total_hectares = fields.Float(
        string="Hectáreas", compute="_compute_totals", store=True, digits=(16, 4),
    )
    total_plants = fields.Float(
        string="Plantas", compute="_compute_totals", store=True, digits=(16, 2),
    )
    total_ue = fields.Float(
        string="Total UE", compute="_compute_totals", store=True, digits=(16, 4),
    )
    total_kg = fields.Float(
        string="Total kg", compute="_compute_totals", store=True, digits=KG_PRECISION_NAME,
    )
    kg_per_ha = fields.Float(
        string="kg / ha", compute="_compute_totals", store=True, digits=(16, 2),
        help="0 cuando no hay hectáreas; nunca división por cero.",
    )
    kg_per_plant = fields.Float(
        string="kg / planta", compute="_compute_totals", store=True, digits=(16, 4),
        help="0 cuando no hay plantas; nunca división por cero.",
    )

    state = fields.Selection(
        [("draft", "Borrador"), ("validated", "Validada"),
         ("superseded", "Reemplazada")],
        string="Estado", default="draft", required=True, index=True, tracking=True,
    )
    revision = fields.Integer(string="Revisión", default=1, copy=False, tracking=True)
    revision_of_id = fields.Many2one(
        "step.management.estimation", string="Revisión de", copy=False,
        ondelete="set null", readonly=True,
    )
    superseded_by_id = fields.Many2one(
        "step.management.estimation", string="Reemplazada por", copy=False,
        ondelete="set null", readonly=True,
    )
    reopen_reason = fields.Text(string="Motivo de la revisión", copy=False, readonly=True)
    import_id = fields.Many2one(
        "step.management.estimation.import", string="Carga de origen",
        readonly=True, copy=False,
    )
    validated_by_id = fields.Many2one(
        "res.users", string="Validada por", readonly=True, copy=False,
    )
    validated_at = fields.Datetime(string="Validada el", readonly=True, copy=False)
    validation_snapshot = fields.Text(
        string="Snapshot de validación", copy=False, readonly=True,
        help="Copia congelada (JSON) de líneas y distribuciones al validar.",
    )
    validation_hash = fields.Char(
        string="Hash del snapshot", size=64, copy=False, readonly=True,
    )
    notes = fields.Html(string="Notas y supuestos")
    active = fields.Boolean(default=True)

    # ------------------------------------------------------------------
    # Cálculos
    # ------------------------------------------------------------------
    @api.depends(
        "line_ids.hectares", "line_ids.plants", "line_ids.total_ue",
        "line_ids.total_kg",
    )
    def _compute_totals(self):
        for record in self:
            record.total_hectares = sum(record.line_ids.mapped("hectares"))
            record.total_plants = sum(record.line_ids.mapped("plants"))
            record.total_ue = sum(record.line_ids.mapped("total_ue"))
            record.total_kg = sum(record.line_ids.mapped("total_kg"))
            record.kg_per_ha = (
                record.total_kg / record.total_hectares
                if record.total_hectares else 0.0
            )
            record.kg_per_plant = (
                record.total_kg / record.total_plants
                if record.total_plants else 0.0
            )

    def _kg_rounding(self):
        digits = self.env["decimal.precision"].precision_get(KG_PRECISION_NAME)
        return 10 ** (-(digits or 2))

    # ------------------------------------------------------------------
    # Secuencia / onchange
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "step.management.estimation"
                ) or _("Nuevo")
        return super().create(vals_list)

    @api.onchange("version_id")
    def _onchange_version_id(self):
        if self.version_id:
            self.season = self.version_id.season

    @api.constrains("center_ids", "company_id")
    def _check_center_company(self):
        for record in self:
            wrong = record.center_ids.filtered(
                lambda center: center.company_id != record.company_id
            )
            if wrong:
                raise ValidationError(_(
                    "Los centros de costo deben pertenecer a la empresa "
                    "%(company)s: %(centers)s"
                ) % {
                    "company": record.company_id.display_name,
                    "centers": ", ".join(wrong.mapped("display_name")),
                })

    # ------------------------------------------------------------------
    # Detalle: snapshot reproducible por centro/cuartel
    # ------------------------------------------------------------------
    def action_compute_lines(self):
        for record in self:
            if record.state != "draft":
                raise UserError(_(
                    "Sólo puede recalcular el detalle de una estimación en borrador."
                ))
            if not record.center_ids:
                raise UserError(_(
                    "Seleccione al menos un centro de costo / cuartel."
                ))
            existing = {line.center_id.id: line for line in record.line_ids}
            keep = set()
            commands = []
            for center in record.center_ids:
                keep.add(center.id)
                snapshot = {
                    "center_id": center.id,
                    "farm": center.farm,
                    "plot": center.plot,
                    "species": center.species or record.species,
                    "variety": center.variety or record.variety,
                    "hectares": center.hectares,
                    "plants": center.plants,
                }
                if center.id in existing:
                    commands.append((1, existing[center.id].id, snapshot))
                else:
                    snapshot["yield_ue"] = record.default_yield_ue
                    commands.append((0, 0, snapshot))
            for line in record.line_ids:
                if line.center_id.id not in keep:
                    commands.append((2, line.id))
            record.write({"line_ids": commands})
            record.message_post(body=_(
                "Detalle recalculado: %s centro(s)/cuartel(es)."
            ) % len(record.center_ids))
        return True

    # ------------------------------------------------------------------
    # Rol y prerrequisitos de validación
    # ------------------------------------------------------------------
    def _ensure_approver(self):
        if not self.env.user.has_group(APPROVER_GROUP):
            raise UserError(_(
                "Necesita el perfil «Aprobador / Control» de Gestión y Costos "
                "para validar estimaciones."
            ))

    def _curve_by_axis(self):
        self.ensure_one()
        return {
            "week": self.week_curve_id,
            "caliber": self.caliber_curve_id,
            "class": self.class_curve_id,
        }

    def _check_validation_prerequisites(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_(
                "Agregue el detalle por centro/cuartel antes de validar."
            ))
        for axis, curve in self._curve_by_axis().items():
            expected = AXIS_CURVE_TYPE[axis]
            if not curve:
                raise UserError(_(
                    "Falta la curva validada del eje «%s»."
                ) % dict(AXIS_SELECTION)[axis])
            if curve.curve_type != expected:
                raise UserError(_(
                    "La curva %(curve)s no es del tipo «%(type)s»."
                ) % {"curve": curve.display_name,
                     "type": dict(AXIS_SELECTION)[axis]})
            if curve.state != "validated":
                raise UserError(_(
                    "La curva %s no está validada."
                ) % curve.display_name)
            if not curve.active:
                raise UserError(_(
                    "La curva %s está archivada."
                ) % curve.display_name)
            if curve.company_id != self.company_id:
                raise UserError(_(
                    "La curva %s pertenece a otra empresa."
                ) % curve.display_name)

    # ------------------------------------------------------------------
    # Generación determinista de distribuciones (D05 + redondeo/residuo)
    # ------------------------------------------------------------------
    def _axis_distribution_commands(self, axis, curve):
        """Reparte total_kg según la curva. Redondea cada porción a la
        precisión de peso y asigna el residuo a la última línea ordenada."""
        self.ensure_one()
        rounding = self._kg_rounding()
        total = float_round(self.total_kg, precision_rounding=rounding)
        curve_lines = curve.line_ids.sorted(key=lambda cl: (cl.sequence, cl.id))
        count = len(curve_lines)
        running = 0.0
        commands = []
        for index, curve_line in enumerate(curve_lines):
            if index < count - 1:
                kg = float_round(
                    total * curve_line.percentage / 100.0,
                    precision_rounding=rounding,
                )
                running = float_round(running + kg, precision_rounding=rounding)
            else:
                kg = float_round(total - running, precision_rounding=rounding)
            commands.append((0, 0, {
                "axis": axis,
                "sequence": curve_line.sequence,
                "week_number": curve_line.week_number,
                "caliber_group_id": curve_line.caliber_group_id.id,
                "fruit_class_id": curve_line.fruit_class_id.id,
                "dimension_key": curve_line.dimension_key,
                "dimension_name": curve_line.dimension_name,
                "percentage": curve_line.percentage,
                "kg": kg,
            }))
        return commands

    def _check_axis_reconciliation(self):
        self.ensure_one()
        rounding = self._kg_rounding()
        total = float_round(self.total_kg, precision_rounding=rounding)
        for axis in AXIS_CURVE_TYPE:
            axis_lines = self.distribution_ids.filtered(lambda d: d.axis == axis)
            axis_sum = float_round(
                sum(axis_lines.mapped("kg")), precision_rounding=rounding
            )
            if float_compare(axis_sum, total, precision_rounding=rounding) != 0:
                raise UserError(_(
                    "El eje «%(axis)s» suma %(sum).4f kg y no concilia con el "
                    "total %(total).4f kg."
                ) % {"axis": axis, "sum": axis_sum, "total": total})

    def _build_validation_snapshot(self):
        self.ensure_one()
        lines = []
        for line in self.line_ids.sorted(key=lambda l: (l.center_id.id, l.id)):
            lines.append({
                "center": line.center_id.code or line.center_id.display_name,
                "farm": line.farm or "",
                "plot": line.plot or "",
                "species": line.species or "",
                "variety": line.variety or "",
                "hectares": round(line.hectares, 4),
                "plants": round(line.plants, 2),
                "yield_ue": round(line.yield_ue, 6),
                "kg_factor": round(line.kg_factor, 6),
                "total_ue": round(line.total_ue, 4),
                "total_kg": round(line.total_kg, 4),
            })
        distributions = {}
        for axis in AXIS_CURVE_TYPE:
            distributions[axis] = [
                {"dimension_key": dist.dimension_key,
                 "dimension_name": dist.dimension_name,
                 "percentage": round(dist.percentage, 4),
                 "kg": round(dist.kg, 4)}
                for dist in self.distribution_ids
                .filtered(lambda d: d.axis == axis)
                .sorted(key=lambda d: (d.sequence, d.id))
            ]
        payload = {
            "estimation": self.name,
            "revision": self.revision,
            "company": self.company_id.name,
            "version": self.version_id.code,
            "season": self.season,
            "method": self.method,
            "unit": self.unit_id.code,
            "week_curve": self.week_curve_id.code,
            "caliber_curve": self.caliber_curve_id.code,
            "class_curve": self.class_curve_id.code,
            "total_hectares": round(self.total_hectares, 4),
            "total_plants": round(self.total_plants, 2),
            "total_ue": round(self.total_ue, 4),
            "total_kg": round(self.total_kg, 4),
            "lines": lines,
            "distributions": distributions,
        }
        return json.dumps(payload, sort_keys=True, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Acciones de estado
    # ------------------------------------------------------------------
    def action_validate(self):
        self._ensure_approver()
        for record in self:
            if record.state != "draft":
                raise UserError(_(
                    "Sólo puede validar una estimación en borrador."
                ))
            record._check_validation_prerequisites()
            # Asegura los campos calculados almacenados del detalle.
            record.line_ids._recompute_recordset(["total_ue", "total_kg"])
            record.invalidate_recordset(["total_kg", "total_ue"])
            rounding = record._kg_rounding()
            if float_compare(record.total_kg, 0.0, precision_rounding=rounding) <= 0:
                raise UserError(_(
                    "El total de kilos debe ser mayor que cero para validar."
                ))
            # Regeneración determinista e idempotente (misma transacción).
            commands = [(5, 0, 0)]
            for axis, curve in record._curve_by_axis().items():
                commands += record._axis_distribution_commands(axis, curve)
            record.write({"distribution_ids": commands})
            record._check_axis_reconciliation()
            snapshot = record._build_validation_snapshot()
            record.write({
                "state": "validated",
                "validated_by_id": self.env.user.id,
                "validated_at": fields.Datetime.now(),
                "validation_snapshot": snapshot,
                "validation_hash": hashlib.sha256(
                    snapshot.encode("utf-8")
                ).hexdigest(),
            })
            record.message_post(body=_(
                "Estimación validada por %(user)s. Snapshot congelado "
                "(hash %(hash)s…)."
            ) % {"user": self.env.user.display_name,
                 "hash": record.validation_hash[:12]})
            origin = record.revision_of_id
            if origin and origin.state == "validated":
                origin.write({
                    "state": "superseded",
                    "superseded_by_id": record.id,
                })
                origin.message_post(body=_(
                    "Reemplazada por la revisión %(rev)s (%(name)s)."
                ) % {"rev": record.revision, "name": record.name})
        return True

    def _create_revision(self, reason=None):
        self.ensure_one()
        self._ensure_approver()
        if self.state != "validated":
            raise UserError(_(
                "Sólo una estimación validada puede revisarse."
            ))
        existing = self.search([
            ("revision_of_id", "=", self.id),
            ("state", "!=", "superseded"),
        ], limit=1)
        if existing:
            raise UserError(_(
                "Ya existe la revisión %(name)s en estado %(state)s. Continúe "
                "o descártela antes de crear otra."
            ) % {"name": existing.display_name, "state": existing.state})
        children = self.search([("revision_of_id", "=", self.id)])
        next_revision = max(children.mapped("revision") or [self.revision]) + 1
        revision = self.copy({
            "revision": next_revision,
            "revision_of_id": self.id,
            "reopen_reason": (reason or "").strip() or False,
        })
        self.message_post(body=_(
            "Se creó la revisión %(rev)s (%(name)s). Esta estimación permanece "
            "inmutable y vigente hasta que la revisión sea validada."
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
            "res_model": "step.management.estimation",
            "res_id": revision.id,
            "view_mode": "form",
            "target": "current",
        }

    # ------------------------------------------------------------------
    # Inmutabilidad
    # ------------------------------------------------------------------
    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {})
        default.setdefault("name", _("Nuevo"))
        default.setdefault("state", "draft")
        default.update({
            "validated_by_id": False,
            "validated_at": False,
            "validation_snapshot": False,
            "validation_hash": False,
            "superseded_by_id": False,
        })
        return super().copy(default)

    def write(self, vals):
        touched = PROTECTED_HEADER_FIELDS & set(vals)
        if touched:
            frozen = self.filtered(lambda record: record.state in FROZEN_STATES)
            if frozen:
                raise UserError(_(
                    "La estimación %(names)s está validada/reemplazada y no "
                    "admite cambios en: %(fields)s. Cree una nueva revisión."
                ) % {
                    "names": ", ".join(frozen.mapped("name")),
                    "fields": ", ".join(sorted(touched)),
                })
        return super().write(vals)

    def unlink(self):
        blocked = self.filtered(lambda record: record.state in FROZEN_STATES)
        if blocked and not self.env.user.has_group(MANAGER_GROUP):
            raise UserError(_(
                "Sólo un administrador puede eliminar estimaciones "
                "validadas/reemplazadas: %s"
            ) % ", ".join(blocked.mapped("name")))
        if blocked:
            raise UserError(_(
                "No se puede eliminar una estimación validada/reemplazada "
                "(%s). Su trazabilidad debe conservarse."
            ) % ", ".join(blocked.mapped("name")))
        return super().unlink()


class StepManagementEstimationLine(models.Model):
    _name = "step.management.estimation.line"
    _description = "Línea de estimación de cosecha"
    _order = "estimation_id, center_id, id"
    _check_company_auto = True

    estimation_id = fields.Many2one(
        "step.management.estimation", string="Estimación", required=True,
        ondelete="cascade", check_company=True, index=True,
    )
    company_id = fields.Many2one(
        related="estimation_id.company_id", string="Empresa", store=True, index=True,
    )
    center_id = fields.Many2one(
        "step.management.cost.center", string="Centro de costo / cuartel",
        required=True, check_company=True, index=True,
    )
    # Snapshot reproducible copiado del centro de costo.
    farm = fields.Char(string="Fundo")
    plot = fields.Char(string="Cuartel")
    species = fields.Char(string="Especie")
    variety = fields.Char(string="Variedad")
    hectares = fields.Float(string="Hectáreas", digits=(16, 4))
    plants = fields.Float(string="Plantas", digits=(16, 2))

    method = fields.Selection(
        related="estimation_id.method", string="Método", store=True,
    )
    unit_id = fields.Many2one(
        related="estimation_id.unit_id", string="Unidad de estimación", store=True,
    )
    kg_factor = fields.Float(
        string="Factor kg", compute="_compute_kg_factor", store=True,
        readonly=False, digits=(16, 6),
        help="Se toma de la unidad de estimación al crear la línea y queda "
             "congelado como snapshot: un cambio posterior del maestro no "
             "altera una estimación ya validada.",
    )
    yield_ue = fields.Float(
        string="Rendimiento (UE)", digits=(16, 6),
        help="Unidades de estimación por planta o por hectárea, según el método.",
    )
    total_kg_input = fields.Float(
        string="Kilos ingresados", digits=KG_PRECISION_NAME,
        help="Sólo para el método «Kilos»: total_kg se ingresa aquí y no se "
             "aplica ninguna otra multiplicación.",
    )
    total_ue = fields.Float(
        string="Total UE", compute="_compute_formula", store=True, digits=(16, 4),
    )
    total_kg = fields.Float(
        string="Total kg", compute="_compute_formula", store=True,
        digits=KG_PRECISION_NAME,
    )
    kg_per_ha = fields.Float(
        string="kg / ha", compute="_compute_ratios", digits=(16, 2),
        help="0 cuando no hay hectáreas; nunca división por cero.",
    )
    kg_per_plant = fields.Float(
        string="kg / planta", compute="_compute_ratios", digits=(16, 4),
        help="0 cuando no hay plantas; nunca división por cero.",
    )

    @api.depends("unit_id")
    def _compute_kg_factor(self):
        for line in self:
            if line.unit_id:
                line.kg_factor = line.unit_id.kg_factor
            elif not line.kg_factor:
                line.kg_factor = 1.0

    @api.depends(
        "method", "plants", "hectares", "yield_ue", "kg_factor", "total_kg_input",
    )
    def _compute_formula(self):
        """Fórmula D05. Nunca multiplica dos veces por rendimiento_ue."""
        for line in self:
            if line.method == "plants":
                line.total_ue = line.plants * line.yield_ue
                line.total_kg = line.total_ue * line.kg_factor
            elif line.method == "hectares":
                line.total_ue = line.hectares * line.yield_ue
                line.total_kg = line.total_ue * line.kg_factor
            elif line.method == "kilos":
                line.total_kg = line.total_kg_input
                line.total_ue = (
                    line.total_kg / line.kg_factor if line.kg_factor else 0.0
                )
            else:
                line.total_ue = 0.0
                line.total_kg = 0.0

    @api.depends("total_kg", "hectares", "plants")
    def _compute_ratios(self):
        for line in self:
            line.kg_per_ha = line.total_kg / line.hectares if line.hectares else 0.0
            line.kg_per_plant = (
                line.total_kg / line.plants if line.plants else 0.0
            )

    @api.constrains("hectares", "plants", "yield_ue")
    def _check_non_negative(self):
        for line in self:
            if line.hectares < 0 or line.plants < 0 or line.yield_ue < 0:
                raise ValidationError(_(
                    "Hectáreas, plantas y rendimiento no pueden ser negativos."
                ))

    _sql_constraints = [
        ("estimation_line_center_unique", "unique(estimation_id, center_id)",
         "No puede repetir el mismo centro de costo en una estimación."),
    ]

    def _assert_editable(self, vals_keys):
        if PROTECTED_LINE_FIELDS & set(vals_keys):
            frozen = self.filtered(
                lambda line: line.estimation_id.state in FROZEN_STATES
            )
            if frozen:
                raise UserError(_(
                    "El detalle de una estimación validada es inmutable. "
                    "Cree una nueva revisión."
                ))

    @api.model_create_multi
    def create(self, vals_list):
        estimations = self.env["step.management.estimation"].browse([
            vals.get("estimation_id") for vals in vals_list if vals.get("estimation_id")
        ])
        if any(est.state in FROZEN_STATES for est in estimations):
            raise UserError(_(
                "No puede agregar líneas a una estimación validada/reemplazada."
            ))
        return super().create(vals_list)

    def write(self, vals):
        self._assert_editable(vals.keys())
        return super().write(vals)

    def unlink(self):
        frozen = self.filtered(
            lambda line: line.estimation_id.state in FROZEN_STATES
        )
        if frozen:
            raise UserError(_(
                "No puede eliminar el detalle de una estimación "
                "validada/reemplazada."
            ))
        return super().unlink()


class StepManagementEstimationDistribution(models.Model):
    _name = "step.management.estimation.distribution"
    _description = "Distribución normalizada de estimación"
    _order = "estimation_id, axis, sequence, id"
    _check_company_auto = True

    estimation_id = fields.Many2one(
        "step.management.estimation", string="Estimación", required=True,
        ondelete="cascade", check_company=True, index=True,
    )
    company_id = fields.Many2one(
        related="estimation_id.company_id", string="Empresa", store=True, index=True,
    )
    axis = fields.Selection(AXIS_SELECTION, string="Eje", required=True, index=True)
    sequence = fields.Integer(default=10)
    week_number = fields.Integer(string="Semana")
    caliber_group_id = fields.Many2one(
        "step.management.caliber.group", string="Grupo de calibre",
        check_company=True, ondelete="restrict",
    )
    fruit_class_id = fields.Many2one(
        "step.management.fruit.class", string="Clase de fruta",
        check_company=True, ondelete="restrict",
    )
    dimension_key = fields.Char(string="Clave", index=True)
    dimension_name = fields.Char(string="Dimensión")
    percentage = fields.Float(string="Porcentaje", digits=(16, 4))
    kg = fields.Float(string="Kilos", digits=KG_PRECISION_NAME)

    def _assert_parent_editable(self):
        frozen = self.filtered(
            lambda dist: dist.estimation_id.state in FROZEN_STATES
        )
        if frozen:
            raise UserError(_(
                "La distribución de una estimación validada es inmutable. "
                "Cree una nueva revisión."
            ))

    @api.model_create_multi
    def create(self, vals_list):
        estimations = self.env["step.management.estimation"].browse([
            vals.get("estimation_id") for vals in vals_list if vals.get("estimation_id")
        ])
        if any(est.state in FROZEN_STATES for est in estimations):
            raise UserError(_(
                "La distribución de una estimación validada es inmutable."
            ))
        return super().create(vals_list)

    def write(self, vals):
        self._assert_parent_editable()
        return super().write(vals)

    def unlink(self):
        self._assert_parent_editable()
        return super().unlink()
