"""Fase 5/7 — motor común de programas fitosanitarios y de fertilización.

Un programa es una receta **por hectárea** (producto, dosis/ha, momento,
objetivo) definida por **temporada y centro de costo** (respuesta del
cliente, Corte 1 post Fase 6): el cuartel es un atributo del centro, no una
unidad seleccionable aparte, y todos los centros incluidos en un mismo
programa deben corresponder a la misma variedad. Al calcular se amplifica
por las hectáreas de cada centro seleccionado: `cantidad = dosis_ha *
hectareas` — **siempre** se multiplica por hectáreas, también en
fertilización (corrige la contradicción C2).

Valorización (D07, pendiente de validación de Compras/Contabilidad): política
configurable por programa. Al aprobar se congela precio, fuente, fecha, moneda
y unidad en un snapshot reproducible con hash; el aprobado es inmutable y sólo
se corrige creando una revisión (sin bypass por contexto RPC).

No se acopla a la Orden de Producción (Fase 6).
"""

import hashlib
import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

APPROVER_GROUP = "step_management_costs.group_management_approver"
MANAGER_GROUP = "step_management_costs.group_management_manager"

FROZEN_STATES = ("approved", "superseded")

PROGRAM_TYPES = [("phyto", "Fitosanitario"), ("fert", "Fertilización")]
PRICE_POLICIES = [
    ("standard", "Costo estándar del producto"),
    ("last_invoice", "Última factura de compra"),
    ("manual", "Precio manual en la línea"),
]

PROTECTED_HEADER_FIELDS = {
    "company_id", "program_type", "season", "species", "variety",
    "price_policy", "currency_id", "center_ids", "line_ids", "application_ids",
}
PROTECTED_LINE_FIELDS = {
    "product_id", "dose_per_ha", "uom_id", "manual_price", "target",
    "week_number", "phi_days", "rei_hours",
}


# ----------------------------------------------------------------------
# R4 (revisión post Corte 1) — coherencia completa de variedad, compartida
# entre `crop_program.py` y `crop_program_import.py` para no duplicar la
# regla. Normaliza con `strip().casefold()` (antes sólo `strip()`), compara
# la variedad del encabezado contra la de los centros y trata la mezcla de
# centros con/sin variedad informada como error (antes se ignoraba el
# centro vacío, lo que permitía mezclar sin evidencia de que fueran la
# misma variedad).
# ----------------------------------------------------------------------
def _variety_issue(centers, header_variety=None):
    """`None` si la combinación de centros (y variedad de encabezado, si se
    pasa) es coherente; si no, un mensaje de error listo para mostrar."""
    informed = [(center, (center.variety or "").strip()) for center in centers]
    non_blank = [(center, value) for center, value in informed if value]
    blank = [center for center, value in informed if not value]
    normalized = {}
    for center, value in non_blank:
        normalized.setdefault(value.casefold(), (value, []))[1].append(center)

    if non_blank and blank:
        return _(
            "Mezcla centros con variedad informada (%(with)s) y sin "
            "variedad (%(without)s): no se puede demostrar que sean de la "
            "misma variedad."
        ) % {
            "with": ", ".join(sorted({c.display_name for c, _v in non_blank})),
            "without": ", ".join(sorted(c.display_name for c in blank)),
        }
    if len(normalized) > 1:
        return _(
            "Los centros de costo deben corresponder a la misma variedad; "
            "se encontraron: %(varieties)s."
        ) % {"varieties": ", ".join(sorted(v for v, _c in normalized.values()))}

    header = (header_variety or "").strip()
    if normalized:
        center_variety = next(iter(normalized.values()))[0]
        if header and header.casefold() != center_variety.casefold():
            return _(
                "La variedad del encabezado («%(header)s») no coincide con "
                "la de los centros («%(center)s»)."
            ) % {"header": header, "center": center_variety}
    return None


def check_center_variety_coherence(centers, header_variety=None):
    """Lanza `ValidationError` si hay un problema de coherencia; si no,
    devuelve la variedad inferida de los centros (o `None` si todos están
    vacíos — permitido para guardar, bloqueado sólo al aprobar)."""
    issue = _variety_issue(centers, header_variety)
    if issue:
        raise ValidationError(issue)
    varieties = {(center.variety or "").strip() for center in centers} - {""}
    return next(iter(varieties)) if varieties else None


class StepManagementCropProgram(models.Model):
    _name = "step.management.crop.program"
    _description = "Programa fitosanitario / de fertilización"
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
    program_type = fields.Selection(
        PROGRAM_TYPES, string="Tipo de programa", required=True,
        default="phyto", index=True, tracking=True,
    )
    season = fields.Char(string="Temporada", required=True, tracking=True, help="Ej.: 2026/2027")
    species = fields.Char(string="Especie", tracking=True)
    variety = fields.Char(string="Variedad", tracking=True)
    date = fields.Date(
        string="Fecha", required=True, default=fields.Date.context_today, tracking=True,
    )
    currency_id = fields.Many2one(
        "res.currency", string="Moneda", required=True,
        default=lambda self: self.env.company.currency_id,
    )
    price_policy = fields.Selection(
        PRICE_POLICIES, string="Política de precio", required=True,
        default="standard", tracking=True,
        help="Fuente del precio unitario al aprobar. Se congela en el snapshot.",
    )
    center_ids = fields.Many2many(
        "step.management.cost.center", "step_management_crop_program_center_rel",
        "program_id", "center_id", string="Centros de costo",
        domain="[('company_id', '=', company_id)]",
        help="Centros de costo de la temporada. El cuartel es un atributo "
             "del centro (campo «Cuartel»), no una unidad seleccionable "
             "aparte. Todos los centros de un mismo programa deben "
             "compartir la misma variedad.",
    )
    line_ids = fields.One2many(
        "step.management.crop.program.line", "program_id", string="Receta por hectárea",
        copy=True,
    )
    application_ids = fields.One2many(
        "step.management.crop.program.application", "program_id",
        string="Aplicaciones expandidas", copy=False,
    )

    total_hectares = fields.Float(
        string="Hectáreas", compute="_compute_totals", store=True, digits=(16, 4),
    )
    total_amount = fields.Monetary(
        string="Costo del programa", compute="_compute_totals", store=True,
        currency_field="currency_id",
    )
    cost_per_ha = fields.Monetary(
        string="Costo por hectárea", compute="_compute_totals", store=True,
        currency_field="currency_id",
    )
    line_count = fields.Integer(compute="_compute_totals", store=True)

    state = fields.Selection(
        [("draft", "Borrador"), ("approved", "Aprobado"),
         ("superseded", "Reemplazado")],
        string="Estado", default="draft", required=True, index=True, tracking=True,
    )
    revision = fields.Integer(string="Revisión", default=1, copy=False, tracking=True)
    revision_of_id = fields.Many2one(
        "step.management.crop.program", string="Revisión de", copy=False,
        ondelete="set null", readonly=True,
    )
    superseded_by_id = fields.Many2one(
        "step.management.crop.program", string="Reemplazado por", copy=False,
        ondelete="set null", readonly=True,
    )
    reopen_reason = fields.Text(string="Motivo de la revisión", copy=False, readonly=True)
    approved_by_id = fields.Many2one(
        "res.users", string="Aprobado por", readonly=True, copy=False, tracking=True,
    )
    approved_at = fields.Datetime(string="Fecha de aprobación", readonly=True, copy=False)
    approval_snapshot = fields.Text(
        string="Snapshot de aprobación", copy=False, readonly=True,
        help="Copia congelada (JSON) de la receta, la expansión y los precios "
             "al aprobar.",
    )
    approval_hash = fields.Char(
        string="Hash del snapshot", size=64, copy=False, readonly=True,
    )
    notes = fields.Html(string="Notas y supuestos")
    active = fields.Boolean(default=True)

    @api.depends("center_ids.hectares", "application_ids.amount", "line_ids")
    def _compute_totals(self):
        for record in self:
            # Hectáreas del programa = suma de los centros cubiertos (no de las
            # aplicaciones, que repiten el centro por cada línea de receta).
            record.total_hectares = sum(record.center_ids.mapped("hectares"))
            record.total_amount = sum(record.application_ids.mapped("amount"))
            record.cost_per_ha = (
                record.total_amount / record.total_hectares
                if record.total_hectares else 0.0
            )
            record.line_count = len(record.line_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "step.management.crop.program"
                ) or _("Nuevo")
        return super().create(vals_list)

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

    @api.constrains("center_ids", "variety")
    def _check_center_variety(self):
        # Respuesta del cliente (Corte 1 post Fase 6) + R4 (revisión): los
        # centros de un mismo programa deben corresponder a la misma
        # variedad, coherente con la variedad del encabezado si está
        # informada. Regla compartida con `crop_program_import.py`.
        for record in self:
            issue = _variety_issue(record.center_ids, record.variety)
            if issue:
                raise ValidationError(_(
                    "Programa %(name)s: %(issue)s"
                ) % {"name": record.name, "issue": issue})

    @api.onchange("center_ids")
    def _onchange_center_ids_infer_variety(self):
        # Conveniencia de UI (R4): completa la variedad del encabezado sólo
        # si está vacía y la inferencia de los centros es inequívoca. Nunca
        # sobrescribe un valor ya informado.
        if not self.variety:
            varieties = {
                (center.variety or "").strip() for center in self.center_ids
            } - {""}
            if len(varieties) == 1:
                self.variety = next(iter(varieties))

    # ------------------------------------------------------------------
    # Expansión por centro (amplificación por hectáreas, C2)
    # ------------------------------------------------------------------
    def action_compute_applications(self):
        for program in self:
            if program.state != "draft":
                raise UserError(_(
                    "Sólo se puede recalcular un programa en borrador."
                ))
            if not program.line_ids:
                raise UserError(_("Agregue al menos una línea a la receta."))
            if not program.center_ids:
                raise UserError(_(
                    "Seleccione al menos un centro de costo / cuartel."
                ))
            invalid = program.center_ids.filtered(lambda c: c.hectares <= 0)
            if invalid:
                raise UserError(_(
                    "Todos los centros deben tener hectáreas mayores que cero: %s"
                ) % ", ".join(invalid.mapped("display_name")))

            program.application_ids.unlink()
            commands = []
            for line in program.line_ids:
                for center in program.center_ids:
                    commands.append((0, 0, {
                        "line_id": line.id,
                        "center_id": center.id,
                        "hectares": center.hectares,
                        "dose_per_ha": line.dose_per_ha,
                        "week_number": line.week_number,
                        "target": line.target,
                        "phi_days": line.phi_days,
                        "rei_hours": line.rei_hours,
                    }))
            program.write({"application_ids": commands})
            program.message_post(body=_(
                "Programa expandido: %(lines)s línea(s) × %(centers)s centro(s) "
                "= %(apps)s aplicación(es)."
            ) % {
                "lines": len(program.line_ids),
                "centers": len(program.center_ids),
                "apps": len(commands),
            })
        return True

    # ------------------------------------------------------------------
    # Valorización
    # ------------------------------------------------------------------
    def _resolve_unit_price(self, application):
        """Precio unitario según la política del programa (D07)."""
        self.ensure_one()
        product = application.line_id.product_id
        policy = self.price_policy
        if policy == "manual":
            return application.line_id.manual_price, _("Precio manual"), self.date
        if policy == "last_invoice":
            move_line = self.env["account.move.line"].search([
                ("product_id", "=", product.id),
                ("company_id", "=", self.company_id.id),
                ("parent_state", "=", "posted"),
                ("move_id.move_type", "in", ("in_invoice", "in_refund")),
                ("price_unit", ">", 0),
            ], order="date desc, id desc", limit=1)
            if move_line:
                return move_line.price_unit, _("Factura %s") % move_line.move_id.name, move_line.date
        # standard (y fallback de last_invoice sin facturas)
        return (
            product.with_company(self.company_id).standard_price,
            _("Costo estándar"),
            self.date,
        )

    def _build_approval_snapshot(self):
        self.ensure_one()
        recipe = []
        for line in self.line_ids.sorted(key=lambda l: (l.sequence, l.id)):
            recipe.append({
                "product": line.product_id.default_code or line.product_id.name,
                "dose_per_ha": round(line.dose_per_ha, 4),
                "uom": line.uom_id.name or "",
                "target": line.target or "",
                "week_number": line.week_number or 0,
                "phi_days": line.phi_days or 0,
                "rei_hours": line.rei_hours or 0,
            })
        applications = []
        for app in self.application_ids.sorted(
            key=lambda a: (a.center_id.id, a.line_id.id, a.id)
        ):
            applications.append({
                "center": app.center_id.code or app.center_id.display_name,
                "product": app.line_id.product_id.default_code or app.line_id.product_id.name,
                "hectares": round(app.hectares, 4),
                "dose_per_ha": round(app.dose_per_ha, 4),
                "quantity": round(app.quantity, 4),
                "unit_price": round(app.unit_price, 6),
                "price_source": app.price_source or "",
                "price_date": fields.Date.to_string(app.price_date),
                "amount": round(app.amount, 2),
            })
        payload = {
            "program": self.name,
            "revision": self.revision,
            "company": self.company_id.name,
            "program_type": self.program_type,
            "season": self.season,
            "currency": self.currency_id.name,
            "price_policy": self.price_policy,
            "total_hectares": round(self.total_hectares, 4),
            "total_amount": round(self.total_amount, 2),
            "recipe": recipe,
            "applications": applications,
        }
        return json.dumps(payload, sort_keys=True, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Acciones de estado
    # ------------------------------------------------------------------
    def _ensure_approver(self):
        if not self.env.user.has_group(APPROVER_GROUP):
            raise UserError(_(
                "Necesita el perfil «Aprobador / Control» de Gestión y Costos "
                "para esta acción."
            ))

    def action_approve(self):
        self._ensure_approver()
        for record in self:
            if record.state != "draft":
                raise UserError(_("Sólo se puede aprobar un programa en borrador."))
            if not record.application_ids:
                raise UserError(_(
                    "Calcule las aplicaciones antes de aprobar el programa."
                ))
            # R4: si ningún centro tiene variedad informada, no hay cómo
            # demostrar que correspondan a la misma variedad. Se permite
            # guardar/calcular en borrador, pero no aprobar así.
            if not any((center.variety or "").strip() for center in record.center_ids):
                raise UserError(_(
                    "Ningún centro de costo del programa %(name)s tiene "
                    "variedad informada: no se puede demostrar que "
                    "correspondan a la misma variedad. Complete la "
                    "variedad de los centros antes de aprobar."
                ) % {"name": record.name})
            # R5: dosis cero sin confirmación del cliente se permite en
            # borrador (con advertencia implícita) pero bloquea la
            # aprobación — ver DECISION_LOG.md.
            zero_dose_lines = record.line_ids.filtered(
                lambda line: line.dose_per_ha == 0
            )
            if zero_dose_lines:
                raise UserError(_(
                    "El programa %(name)s tiene línea(s) de receta con "
                    "dosis por hectárea igual a cero (%(products)s). "
                    "Corríjalas o elimínelas antes de aprobar."
                ) % {
                    "name": record.name,
                    "products": ", ".join(
                        zero_dose_lines.mapped("product_id.display_name")
                    ),
                })
            for application in record.application_ids:
                price, source, price_date = record._resolve_unit_price(application)
                application.write({
                    "unit_price": price,
                    "price_source": source,
                    "price_date": price_date,
                })
            record.application_ids._recompute_recordset(["amount"])
            record.invalidate_recordset(["total_amount", "cost_per_ha"])
            snapshot = record._build_approval_snapshot()
            record.write({
                "state": "approved",
                "approved_by_id": self.env.user.id,
                "approved_at": fields.Datetime.now(),
                "approval_snapshot": snapshot,
                "approval_hash": hashlib.sha256(
                    snapshot.encode("utf-8")
                ).hexdigest(),
            })
            record.message_post(body=_(
                "Programa aprobado por %(user)s. Snapshot congelado "
                "(hash %(hash)s…)."
            ) % {"user": self.env.user.display_name,
                 "hash": record.approval_hash[:12]})
            origin = record.revision_of_id
            if origin and origin.state == "approved":
                origin.write({
                    "state": "superseded",
                    "superseded_by_id": record.id,
                })
                origin.message_post(body=_(
                    "Reemplazado por la revisión %(rev)s (%(name)s)."
                ) % {"rev": record.revision, "name": record.name})
        return True

    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {})
        default.setdefault("name", _("Nuevo"))
        default.setdefault("state", "draft")
        default.update({
            "approved_by_id": False,
            "approved_at": False,
            "approval_snapshot": False,
            "approval_hash": False,
            "superseded_by_id": False,
        })
        return super().copy(default)

    def action_duplicate(self):
        """Copia independiente (p. ej. misma receta, otra temporada)."""
        self.ensure_one()
        new = self.copy({"revision_of_id": False, "reopen_reason": False})
        return {
            "type": "ir.actions.act_window",
            "res_model": "step.management.crop.program",
            "res_id": new.id, "view_mode": "form", "target": "current",
        }

    def _create_revision(self, reason=None):
        self.ensure_one()
        self._ensure_approver()
        if self.state != "approved":
            raise UserError(_(
                "Sólo un programa aprobado puede revisarse."
            ))
        existing = self.search([
            ("revision_of_id", "=", self.id),
            ("state", "!=", "superseded"),
        ], limit=1)
        if existing:
            raise UserError(_(
                "Ya existe la revisión %(name)s en estado %(state)s."
            ) % {"name": existing.display_name, "state": existing.state})
        children = self.search([("revision_of_id", "=", self.id)])
        next_revision = max(children.mapped("revision") or [self.revision]) + 1
        revision = self.copy({
            "revision": next_revision,
            "revision_of_id": self.id,
            "reopen_reason": (reason or "").strip() or False,
        })
        self.message_post(body=_(
            "Se creó la revisión %(rev)s (%(name)s). Este programa permanece "
            "inmutable y vigente hasta que la revisión sea aprobada."
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
            "res_model": "step.management.crop.program",
            "res_id": revision.id, "view_mode": "form", "target": "current",
        }

    # ------------------------------------------------------------------
    # Inmutabilidad
    # ------------------------------------------------------------------
    def write(self, vals):
        touched = PROTECTED_HEADER_FIELDS & set(vals)
        if touched:
            frozen = self.filtered(lambda record: record.state in FROZEN_STATES)
            if frozen:
                raise UserError(_(
                    "El programa %(names)s está aprobado/reemplazado y no admite "
                    "cambios en: %(fields)s. Cree una nueva revisión."
                ) % {
                    "names": ", ".join(frozen.mapped("name")),
                    "fields": ", ".join(sorted(touched)),
                })
        return super().write(vals)

    def unlink(self):
        blocked = self.filtered(lambda record: record.state in FROZEN_STATES)
        if blocked and not self.env.user.has_group(MANAGER_GROUP):
            raise UserError(_(
                "Sólo un administrador puede eliminar programas "
                "aprobados/reemplazados: %s"
            ) % ", ".join(blocked.mapped("name")))
        if blocked:
            raise UserError(_(
                "No se puede eliminar un programa aprobado/reemplazado (%s). Su "
                "trazabilidad debe conservarse."
            ) % ", ".join(blocked.mapped("name")))
        return super().unlink()


class StepManagementCropProgramLine(models.Model):
    _name = "step.management.crop.program.line"
    _description = "Línea de receta del programa (por hectárea)"
    _order = "program_id, sequence, id"
    _check_company_auto = True

    program_id = fields.Many2one(
        "step.management.crop.program", string="Programa", required=True,
        ondelete="cascade", check_company=True, index=True,
    )
    company_id = fields.Many2one(
        related="program_id.company_id", string="Empresa", store=True, index=True,
    )
    program_type = fields.Selection(
        related="program_id.program_type", string="Tipo", store=True,
    )
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one(
        "product.product", string="Producto", required=True, check_company=True,
    )
    dose_per_ha = fields.Float(string="Dosis por hectárea", digits=(16, 4), required=True)
    uom_id = fields.Many2one("uom.uom", string="Unidad de medida")
    manual_price = fields.Monetary(
        string="Precio manual", currency_field="currency_id",
        help="Se usa cuando la política de precio del programa es «manual».",
    )
    currency_id = fields.Many2one(related="program_id.currency_id", store=True)
    target = fields.Char(
        string="Objetivo / plaga / nutriente",
        help="Plaga u objetivo (fitosanitario) o nutriente (fertilización).",
    )
    week_number = fields.Integer(string="Semana calendario")
    phi_days = fields.Integer(
        string="Carencia (días)", help="Período de carencia previo a cosecha (OT-BPA).",
    )
    rei_hours = fields.Integer(
        string="Reingreso (horas)", help="Período de reingreso al cuartel (OT-BPA).",
    )
    notes = fields.Char(string="Observación")

    @api.constrains("dose_per_ha", "week_number", "phi_days", "rei_hours")
    def _check_values(self):
        for line in self:
            if line.dose_per_ha < 0:
                raise ValidationError(_("La dosis por hectárea no puede ser negativa."))
            if line.week_number and not 1 <= line.week_number <= 53:
                raise ValidationError(_("La semana calendario debe estar entre 1 y 53."))
            if line.phi_days < 0 or line.rei_hours < 0:
                raise ValidationError(_(
                    "La carencia y el reingreso no pueden ser negativos."
                ))

    def _assert_editable(self, vals_keys):
        if PROTECTED_LINE_FIELDS & set(vals_keys):
            frozen = self.filtered(
                lambda line: line.program_id.state in FROZEN_STATES
            )
            if frozen:
                raise UserError(_(
                    "La receta de un programa aprobado es inmutable. Cree una "
                    "nueva revisión."
                ))

    @api.model_create_multi
    def create(self, vals_list):
        programs = self.env["step.management.crop.program"].browse([
            vals.get("program_id") for vals in vals_list if vals.get("program_id")
        ])
        if any(program.state in FROZEN_STATES for program in programs):
            raise UserError(_(
                "No puede agregar líneas a un programa aprobado/reemplazado."
            ))
        return super().create(vals_list)

    def write(self, vals):
        self._assert_editable(vals.keys())
        return super().write(vals)

    def unlink(self):
        frozen = self.filtered(
            lambda line: line.program_id.state in FROZEN_STATES
        )
        if frozen:
            raise UserError(_(
                "No puede eliminar la receta de un programa aprobado/reemplazado."
            ))
        return super().unlink()


class StepManagementCropProgramApplication(models.Model):
    _name = "step.management.crop.program.application"
    _description = "Aplicación expandida del programa (por centro)"
    _order = "program_id, center_id, line_id, id"
    _check_company_auto = True

    program_id = fields.Many2one(
        "step.management.crop.program", string="Programa", required=True,
        ondelete="cascade", check_company=True, index=True,
    )
    company_id = fields.Many2one(
        related="program_id.company_id", string="Empresa", store=True, index=True,
    )
    currency_id = fields.Many2one(related="program_id.currency_id", store=True)
    line_id = fields.Many2one(
        "step.management.crop.program.line", string="Línea de receta",
        required=True, ondelete="cascade", check_company=True, index=True,
    )
    center_id = fields.Many2one(
        "step.management.cost.center", string="Centro de costo / cuartel",
        required=True, check_company=True, index=True,
    )
    product_id = fields.Many2one(
        related="line_id.product_id", string="Producto", store=True,
    )
    uom_id = fields.Many2one(related="line_id.uom_id", string="UdM", store=True)
    hectares = fields.Float(string="Hectáreas", digits=(16, 4))
    dose_per_ha = fields.Float(string="Dosis por hectárea", digits=(16, 4))
    quantity = fields.Float(
        string="Cantidad total", compute="_compute_quantity", store=True, digits=(16, 4),
    )
    unit_price = fields.Monetary(string="Precio unitario", currency_field="currency_id")
    price_source = fields.Char(string="Fuente del precio", readonly=True)
    price_date = fields.Date(string="Fecha del precio", readonly=True)
    amount = fields.Monetary(
        string="Importe", compute="_compute_amount", store=True,
        currency_field="currency_id",
    )
    week_number = fields.Integer(string="Semana")
    target = fields.Char(string="Objetivo")
    phi_days = fields.Integer(string="Carencia (días)")
    rei_hours = fields.Integer(string="Reingreso (horas)")

    _sql_constraints = [
        ("crop_program_application_unique", "unique(line_id, center_id)",
         "Una línea de receta no puede expandirse dos veces al mismo centro."),
    ]

    @api.depends("dose_per_ha", "hectares")
    def _compute_quantity(self):
        # C2: la cantidad SIEMPRE se amplifica por hectáreas.
        for record in self:
            record.quantity = record.dose_per_ha * record.hectares

    @api.depends("quantity", "unit_price")
    def _compute_amount(self):
        for record in self:
            record.amount = record.quantity * record.unit_price

    def _assert_parent_editable(self, vals_keys=None):
        blocked = {
            "line_id", "center_id", "hectares", "dose_per_ha", "unit_price",
            "week_number", "target", "phi_days", "rei_hours",
        }
        if vals_keys is not None and not (blocked & set(vals_keys)):
            return
        frozen = self.filtered(
            lambda app: app.program_id.state in FROZEN_STATES
        )
        if frozen:
            raise UserError(_(
                "Las aplicaciones de un programa aprobado son inmutables. Cree "
                "una nueva revisión."
            ))

    @api.model_create_multi
    def create(self, vals_list):
        programs = self.env["step.management.crop.program"].browse([
            vals.get("program_id") for vals in vals_list if vals.get("program_id")
        ])
        if any(program.state in FROZEN_STATES for program in programs):
            raise UserError(_(
                "Las aplicaciones de un programa aprobado son inmutables."
            ))
        return super().create(vals_list)

    def write(self, vals):
        self._assert_parent_editable(vals.keys())
        return super().write(vals)

    def unlink(self):
        self._assert_parent_editable()
        return super().unlink()
