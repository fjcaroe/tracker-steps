"""Corte 2 — Orden de Producción (OP) semanal central.

Una OP es por **empresa, temporada, año/semana ISO, especie y centro de
costo** (el cuartel es un atributo informativo del centro, no crea otra OP).
Consolida, sin duplicar, dos fuentes ya existentes en el núcleo:

- `step.management.plan.line` (tareas planificadas, generadas desde el
  presupuesto aprobado o manuales, siempre que tengan semana ISO);
- `step.management.crop.program.application` (aplicaciones fito/ferti de un
  programa **aprobado**).

**Cosecha queda fuera de este corte** (decisión temporal, ver
`DECISION_LOG.md`): `harvest.plan.line` es semanal agregado y no tiene
`center_id`; la OP es por centro. No hay forma determinista de repartir
kilos por centro sin inventar un prorrateo, así que no se reparte.

Mismo contrato optimista que R1 (`planning.py`): la generación es una vista
previa sin escritura (`_build_op_commands`) con una huella determinista
(`_op_fingerprint`); `action_authorize` vuelve a comparar la huella antes de
congelar el snapshot, para no autorizar algo distinto de lo último
generado/visto.

Una OP autorizada es inmutable; las correcciones son una nueva revisión
(mismo patrón que `crop_program.py`: snapshot + hash congelados,
`revision`/`revision_of_id`/`superseded_by_id`).

No crea OT ni escribe en addons operacionales: `get_bridge_payload()` es la
única API que el futuro puente podrá consumir, y rechaza cualquier OP no
autorizada.
"""

import base64
import hashlib
import json

from psycopg2 import IntegrityError

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from .crop_program import PROGRAM_TYPES

APPROVER_GROUP = "step_management_costs.group_management_approver"
MANAGER_GROUP = "step_management_costs.group_management_manager"

FROZEN_STATES = ("authorized", "superseded")

PLAN_LINE_INVALID_STATES = ("cancelled",)
PLAN_INVALID_STATES = ("cancelled",)

PROTECTED_HEADER_FIELDS = {
    "company_id", "center_id", "season", "iso_year", "iso_week", "species",
    "monday", "sunday", "line_ids",
}


class StepManagementProductionOrder(models.Model):
    _name = "step.management.production.order"
    _description = "Orden de Producción semanal"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "iso_year desc, iso_week desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        string="Folio", required=True, copy=False, readonly=True,
        default=lambda self: _("Nuevo"), index=True,
    )
    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True,
        default=lambda self: self.env.company, index=True, tracking=True,
    )
    season = fields.Char(string="Temporada", required=True, tracking=True, help="Ej.: 2026/2027")
    iso_year = fields.Integer(string="Año ISO", required=True, tracking=True)
    iso_week = fields.Integer(string="Semana ISO", required=True, tracking=True)
    monday = fields.Date(string="Inicio (lunes)", readonly=True)
    sunday = fields.Date(string="Término (domingo)", readonly=True)
    species = fields.Char(string="Especie", tracking=True)
    species_key = fields.Char(compute="_compute_species_key", store=True)
    center_id = fields.Many2one(
        "step.management.cost.center", string="Centro de costo", required=True,
        check_company=True, tracking=True,
    )

    state = fields.Selection(
        [("draft", "Borrador"), ("authorized", "Autorizada"),
         ("superseded", "Reemplazada"), ("cancelled", "Cancelada")],
        string="Estado", default="draft", required=True, index=True, tracking=True,
    )
    revision = fields.Integer(string="Revisión", default=1, copy=False, tracking=True)
    revision_of_id = fields.Many2one(
        "step.management.production.order", string="Revisión de", copy=False,
        ondelete="set null", readonly=True,
    )
    superseded_by_id = fields.Many2one(
        "step.management.production.order", string="Reemplazada por", copy=False,
        ondelete="set null", readonly=True,
    )
    reopen_reason = fields.Text(string="Motivo de la revisión", copy=False, readonly=True)

    generation_fingerprint = fields.Char(
        string="Huella de generación", size=64, copy=False, readonly=True,
        help="Huella determinista de las fuentes y líneas de la última vista "
             "previa confirmada (mismo contrato que R1). `action_authorize` "
             "vuelve a compararla antes de congelar el snapshot.",
    )
    authorized_by_id = fields.Many2one(
        "res.users", string="Autorizada por", readonly=True, copy=False, tracking=True,
    )
    authorized_at = fields.Datetime(string="Fecha de autorización", readonly=True, copy=False)
    approval_snapshot = fields.Text(
        string="Snapshot de autorización", copy=False, readonly=True,
        help="Copia congelada (JSON) de la cabecera y las líneas al "
             "autorizar. El PDF de una OP autorizada se genera siempre "
             "desde aquí, nunca volviendo a consultar maestros cambiables.",
    )
    approval_hash = fields.Char(string="Hash del snapshot", size=64, copy=False, readonly=True)

    line_ids = fields.One2many(
        "step.management.production.order.line", "order_id", string="Líneas", copy=False,
    )
    line_count = fields.Integer(compute="_compute_line_count", store=True)

    recipient_ids = fields.Many2many(
        "res.partner", string="Destinatarios",
        help="Perfiles configurables (gerente agrícola, jefe de campo, "
             "supervisores, bodega, BPA). Sin destinatarios por defecto: los "
             "usuarios reales del cliente siguen pendientes.",
    )
    send_state = fields.Selection(
        [("not_sent", "No enviada"), ("sent", "Enviada"), ("failed", "Falló")],
        default="not_sent", required=True, copy=False, tracking=True,
        help="«Enviada» significa que se encoló el correo (`mail.mail`); el "
             "envío nunca es condición para autorizar ni altera el snapshot.",
    )
    send_requested_by_id = fields.Many2one(
        "res.users", string="Envío solicitado por", readonly=True, copy=False,
    )
    send_requested_at = fields.Datetime(string="Fecha de envío", readonly=True, copy=False)

    notes = fields.Html(string="Instrucciones / observaciones")
    active = fields.Boolean(default=True)

    @api.depends("species")
    def _compute_species_key(self):
        for record in self:
            record.species_key = (record.species or "").strip().casefold()

    @api.depends("line_ids")
    def _compute_line_count(self):
        for record in self:
            record.line_count = len(record.line_ids)

    def init(self):
        # Identidad + concurrencia: impide de forma transaccional dos OP
        # vigentes/autorizadas para la misma clave natural (empresa, centro,
        # año/semana ISO, especie normalizada). Varias revisiones/borradores
        # con la misma clave conviven en el tiempo — por eso es un índice
        # parcial (sólo `state = 'authorized'`), no un `unique()` plano.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                step_management_production_order_identity_uniq
            ON step_management_production_order
                (company_id, center_id, iso_year, iso_week, species_key)
            WHERE state = 'authorized'
        """)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "step.management.production.order"
                ) or _("Nuevo")
        return super().create(vals_list)

    @api.constrains("species", "center_id")
    def _check_species_matches_center(self):
        for record in self:
            center_species = (record.center_id.species or "").strip()
            header_species = (record.species or "").strip()
            if (
                center_species and header_species
                and center_species.casefold() != header_species.casefold()
            ):
                raise ValidationError(_(
                    "La especie del encabezado («%(header)s») no coincide "
                    "con la del centro de costo «%(center)s» (%(center_species)s)."
                ) % {
                    "header": header_species, "center": record.center_id.display_name,
                    "center_species": center_species,
                })

    # ------------------------------------------------------------------
    # Generación / vista previa (mismo contrato de huella que R1)
    # ------------------------------------------------------------------
    def _build_op_commands(self):
        """Calcula (sin escribir) los comandos de línea desde las fuentes
        válidas de la misma empresa/centro/semana ISO. Devuelve
        `(commands, monday, sunday, fingerprint)`."""
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_(
                "Sólo se puede generar o regenerar una Orden de Producción "
                "en borrador."
            ))
        if not self.center_id:
            raise UserError(_("Seleccione el centro de costo."))
        period = self.env["step.management.period.service"]
        located = period.week_of_season(self.season, self.iso_week)
        if not located or located["iso_year"] != self.iso_year:
            raise UserError(_(
                "La semana %(week)s no corresponde al año ISO %(year)s "
                "dentro de la temporada %(season)s."
            ) % {"week": self.iso_week, "year": self.iso_year, "season": self.season})
        monday, sunday = located["monday"], located["sunday"]

        commands = []

        # Tareas planificadas (F4-A4): mismo centro/semana ISO, plan y tarea
        # no cancelados. Supuesto documentado (abierto, sin confirmación del
        # cliente sobre qué otros estados de tarea califican): sólo se
        # excluye lo explícitamente cancelado.
        plan_lines = self.env["step.management.plan.line"].search([
            ("company_id", "=", self.company_id.id),
            ("center_id", "=", self.center_id.id),
            ("iso_year", "=", self.iso_year),
            ("iso_week", "=", self.iso_week),
            ("plan_id.state", "not in", PLAN_INVALID_STATES),
            ("state", "not in", PLAN_LINE_INVALID_STATES),
        ])
        for line in plan_lines:
            budget_line = line.budget_line_id
            commands.append((0, 0, {
                "source_type": "plan_line",
                "plan_line_id": line.id,
                "description": line.indicator,
                "activity": (budget_line.activity if budget_line else False) or line.indicator,
                "product_id": budget_line.product_id.id if budget_line else False,
                "uom_id": line.uom_id.id,
                "quantity": line.quantity,
                "budget_group_id": budget_line.group_id.id if budget_line else False,
            }))

        # Aplicaciones fito/ferti: sólo de programa aprobado, misma
        # temporada/centro, y semana calendario igual a la semana ISO de la
        # OP (ambas expresadas 1-53 dentro de la misma temporada — no se
        # duplica lógica de calendario, se reutiliza `period_service`).
        program_type_labels = dict(PROGRAM_TYPES)
        applications = self.env["step.management.crop.program.application"].search([
            ("company_id", "=", self.company_id.id),
            ("center_id", "=", self.center_id.id),
            ("week_number", "=", self.iso_week),
            ("program_id.season", "=", self.season),
            ("program_id.state", "=", "approved"),
        ])
        for app in applications:
            commands.append((0, 0, {
                "source_type": "program_application",
                "program_application_id": app.id,
                "description": app.target or app.product_id.display_name,
                "activity": program_type_labels.get(app.program_id.program_type, ""),
                "product_id": app.product_id.id,
                "uom_id": app.uom_id.id,
                "quantity": app.quantity,
                "budget_group_id": False,
            }))

        # Cosecha (V2 A): sólo de un plan de cosecha CONFIRMADO (no
        # borrador, no reemplazado), mismo centro/temporada y semana. Ya
        # resuelve el bloqueo del Corte 2 — `harvest.plan.line` ahora tiene
        # `center_id` (planes generados desde este corte en adelante).
        kg_uom = self.env.ref("uom.product_uom_kgm", raise_if_not_found=False)
        harvest_lines = self.env["step.management.harvest.plan.line"].search([
            ("company_id", "=", self.company_id.id),
            ("center_id", "=", self.center_id.id),
            ("week_number", "=", self.iso_week),
            ("harvest_plan_id.season", "=", self.season),
            ("harvest_plan_id.state", "=", "confirmed"),
        ])
        for hline in harvest_lines:
            commands.append((0, 0, {
                "source_type": "harvest_line",
                "harvest_plan_line_id": hline.id,
                "description": _("Cosecha %s") % (hline.week_label or ""),
                "activity": _("Cosecha"),
                "product_id": False,
                "uom_id": kg_uom.id if kg_uom else False,
                "quantity": hline.kg,
                "budget_group_id": False,
            }))

        fingerprint = self._op_fingerprint(commands)
        return commands, monday, sunday, fingerprint

    def _op_fingerprint(self, commands):
        self.ensure_one()
        payload = {
            "company_id": self.company_id.id, "center_id": self.center_id.id,
            "season": self.season, "iso_year": self.iso_year, "iso_week": self.iso_week,
            "species": (self.species or "").strip().casefold(),
            "commands": [vals for (_op, _zero, vals) in commands],
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()

    def _apply_op_commands(self, commands, monday, sunday, fingerprint):
        self.ensure_one()
        self.line_ids.unlink()
        self.write({
            "line_ids": commands, "monday": monday, "sunday": sunday,
            "generation_fingerprint": fingerprint,
        })
        self.message_post(body=_(
            "Generada(s) %(count)s línea(s) (vista previa confirmada)."
        ) % {"count": len(commands)})

    def action_generate_preview(self):
        self.ensure_one()
        self._build_op_commands()  # valida centro/semana temprano, no escribe
        return {
            "type": "ir.actions.act_window",
            "name": _("Vista previa: generar Orden de Producción"),
            "res_model": "step.management.production.order.preview.wizard",
            "view_mode": "form", "target": "new",
            "context": {"default_order_id": self.id},
        }

    # ------------------------------------------------------------------
    # Autorización, snapshot e inmutabilidad
    # ------------------------------------------------------------------
    def _ensure_approver(self):
        if not self.env.user.has_group(APPROVER_GROUP):
            raise UserError(_(
                "Necesita el perfil «Aprobador / Control» de Gestión y "
                "Costos para esta acción."
            ))

    def _build_snapshot_payload(self):
        self.ensure_one()
        lines = []
        for line in self.line_ids.sorted(key=lambda l: (l.source_type, l.id)):
            lines.append({
                "source_type": line.source_type,
                "description": line.description or "",
                "activity": line.activity or "",
                "budget_group": line.budget_group_id.display_name if line.budget_group_id else "",
                "product": line.product_id.display_name if line.product_id else "",
                "uom": line.uom_id.name if line.uom_id else "",
                "quantity": round(line.quantity, 4),
            })
        return {
            "folio": self.name,
            "revision": self.revision,
            "company": self.company_id.name,
            "season": self.season,
            "iso_year": self.iso_year,
            "iso_week": self.iso_week,
            "monday": fields.Date.to_string(self.monday),
            "sunday": fields.Date.to_string(self.sunday),
            "species": self.species or "",
            "center": self.center_id.display_name,
            "farm": self.center_id.farm or "",
            "plot": self.center_id.plot or "",
            "creator": self.create_uid.display_name if self.create_uid else "",
            "authorizer": self.authorized_by_id.display_name if self.authorized_by_id else "",
            "notes": self.notes or "",
            "lines": lines,
        }

    def action_authorize(self):
        self._ensure_approver()
        for record in self:
            if record.state != "draft":
                raise UserError(_(
                    "Sólo se puede autorizar una Orden de Producción en "
                    "borrador."
                ))
            if not record.line_ids:
                raise UserError(_(
                    "Genere y confirme la vista previa antes de autorizar."
                ))
            # Contrato optimista (R1): recalcula y compara la huella antes
            # de congelar; si las fuentes cambiaron desde la última vista
            # previa confirmada, no autoriza nada.
            _commands, _monday, _sunday, fingerprint = record._build_op_commands()
            if fingerprint != record.generation_fingerprint:
                raise UserError(_(
                    "Las fuentes cambiaron desde la última vista previa "
                    "confirmada. Genere una vista previa nueva antes de "
                    "autorizar."
                ))
            payload = record._build_snapshot_payload()
            snapshot = json.dumps(payload, sort_keys=True, ensure_ascii=False)
            origin = record.revision_of_id
            # Concurrencia: el índice único parcial (`init()`) es quien
            # impide de verdad dos OP vigentes/autorizadas para la misma
            # clave; este `try` sólo traduce la violación a un error legible
            # en vez de dejar pasar un `IntegrityError` crudo. El origen se
            # reemplaza DENTRO del mismo savepoint que la propia
            # autorización — si no, una revisión legítima chocaría consigo
            # misma (origen y revisión comparten la clave natural) mientras
            # el origen siga en estado "authorized".
            try:
                with self.env.cr.savepoint():
                    if origin and origin.state == "authorized":
                        origin.write({"state": "superseded", "superseded_by_id": record.id})
                    record.write({
                        "state": "authorized",
                        "authorized_by_id": self.env.user.id,
                        "authorized_at": fields.Datetime.now(),
                        "approval_snapshot": snapshot,
                        "approval_hash": hashlib.sha256(snapshot.encode("utf-8")).hexdigest(),
                    })
            except IntegrityError as exc:
                raise UserError(_(
                    "Ya existe una Orden de Producción autorizada para la "
                    "misma empresa, centro, año/semana ISO y especie. "
                    "Autorice una revisión de esa OP en lugar de crear otra."
                )) from exc
            record.message_post(body=_(
                "Orden de Producción autorizada por %(user)s. Snapshot "
                "congelado (hash %(hash)s…)."
            ) % {"user": self.env.user.display_name, "hash": record.approval_hash[:12]})
            if origin and origin.state == "superseded":
                origin.message_post(body=_(
                    "Reemplazada por la revisión %(rev)s (%(name)s)."
                ) % {"rev": record.revision, "name": record.name})
        return True

    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {})
        default.setdefault("name", _("Nuevo"))
        default.setdefault("state", "draft")
        default.update({
            "authorized_by_id": False, "authorized_at": False,
            "approval_snapshot": False, "approval_hash": False,
            "superseded_by_id": False, "generation_fingerprint": False,
            "send_state": "not_sent", "send_requested_by_id": False,
            "send_requested_at": False,
        })
        return super().copy(default)

    def _create_revision(self, reason=None):
        self.ensure_one()
        self._ensure_approver()
        if self.state != "authorized":
            raise UserError(_(
                "Sólo una Orden de Producción autorizada puede revisarse."
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
            "Se creó la revisión %(rev)s (%(name)s). Esta OP permanece "
            "inmutable y vigente hasta que la revisión sea autorizada."
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
            "res_model": "step.management.production.order",
            "res_id": revision.id, "view_mode": "form", "target": "current",
        }

    def write(self, vals):
        touched = PROTECTED_HEADER_FIELDS & set(vals)
        if touched:
            frozen = self.filtered(lambda record: record.state in FROZEN_STATES)
            if frozen:
                raise UserError(_(
                    "La OP %(names)s está autorizada/reemplazada y no admite "
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
                "Sólo un administrador puede eliminar OP autorizadas/"
                "reemplazadas: %s"
            ) % ", ".join(blocked.mapped("name")))
        if blocked:
            raise UserError(_(
                "No se puede eliminar una OP autorizada/reemplazada (%s). Su "
                "trazabilidad debe conservarse."
            ) % ", ".join(blocked.mapped("name")))
        return super().unlink()

    def action_cancel(self):
        for record in self:
            if record.state != "draft":
                raise UserError(_("Sólo se puede cancelar una OP en borrador."))
            record.state = "cancelled"

    def action_set_draft(self):
        self.filtered(lambda r: r.state == "cancelled").write({"state": "draft"})

    # ------------------------------------------------------------------
    # PDF (usa el snapshot cuando existe) y envío simulado
    # ------------------------------------------------------------------
    def _report_payload(self):
        self.ensure_one()
        if self.state in ("authorized", "superseded") and self.approval_snapshot:
            return json.loads(self.approval_snapshot)
        # Borrador: conveniencia de impresión con datos en vivo, sin la
        # garantía de estabilidad del snapshot (se documenta así).
        return self._build_snapshot_payload()

    def action_send_report(self):
        self.ensure_one()
        if self.state not in ("authorized", "superseded"):
            raise UserError(_(
                "Sólo se puede enviar una Orden de Producción autorizada."
            ))
        if not self.recipient_ids:
            raise UserError(_("Seleccione al menos un destinatario."))
        report = self.env.ref("step_management_costs.action_report_production_order")
        pdf_content, _ext = report._render_qweb_pdf(
            "step_management_costs.report_production_order", self.ids,
        )
        attachment = self.env["ir.attachment"].create({
            "name": "%s.pdf" % self.name, "type": "binary",
            "datas": base64.b64encode(pdf_content),
            "res_model": self._name, "res_id": self.id,
            "mimetype": "application/pdf",
        })
        # Se encola el correo (`mail.mail`, estado "outgoing"); no se fuerza
        # el envío inmediato aquí — el cron de correo saliente de Odoo es el
        # único que entrega de verdad. En pruebas nunca se llama a un
        # servidor SMTP real porque nunca se invoca `.send()`.
        self.env["mail.mail"].sudo().create({
            "subject": _("Orden de Producción %s") % self.name,
            "body_html": _(
                "<p>Adjunta la Orden de Producción %s.</p>"
            ) % self.name,
            "recipient_ids": [(6, 0, self.recipient_ids.ids)],
            "attachment_ids": [(6, 0, [attachment.id])],
            "auto_delete": False,
        })
        self.write({
            "send_state": "sent",
            "send_requested_by_id": self.env.user.id,
            "send_requested_at": fields.Datetime.now(),
        })
        self.message_post(body=_(
            "Envío de la OP encolado para: %s"
        ) % ", ".join(self.recipient_ids.mapped("display_name")))
        return True

    # ------------------------------------------------------------------
    # API interna para el futuro puente OT (Corte 3) — no crea OT todavía.
    # ------------------------------------------------------------------
    def get_bridge_payload(self):
        self.ensure_one()
        if self.state not in ("authorized", "superseded"):
            raise UserError(_(
                "La integración con Órdenes de Trabajo sólo acepta Órdenes "
                "de Producción autorizadas (estado actual: %s)."
            ) % self.state)
        return json.loads(self.approval_snapshot)


class StepManagementProductionOrderLine(models.Model):
    _name = "step.management.production.order.line"
    _description = "Línea de la Orden de Producción"
    _order = "order_id, source_type, id"
    _check_company_auto = True

    order_id = fields.Many2one(
        "step.management.production.order", string="Orden de Producción",
        required=True, ondelete="cascade", check_company=True, index=True,
    )
    company_id = fields.Many2one(
        related="order_id.company_id", string="Empresa", store=True, index=True,
    )
    source_type = fields.Selection(
        [("plan_line", "Tarea planificada"),
         ("program_application", "Fitosanitario / Fertilización"),
         ("harvest_line", "Cosecha")],
        string="Origen", required=True,
    )
    plan_line_id = fields.Many2one(
        "step.management.plan.line", string="Tarea de origen",
        ondelete="set null", check_company=True, index=True,
    )
    program_application_id = fields.Many2one(
        "step.management.crop.program.application", string="Aplicación de origen",
        ondelete="set null", check_company=True, index=True,
    )
    harvest_plan_line_id = fields.Many2one(
        "step.management.harvest.plan.line", string="Cosecha de origen",
        ondelete="set null", check_company=True, index=True,
    )
    description = fields.Char(string="Descripción")
    activity = fields.Char(string="Actividad")
    budget_group_id = fields.Many2one(
        "step.management.budget.group", string="Grupo presupuesto", check_company=True,
    )
    product_id = fields.Many2one("product.product", string="Producto / labor")
    uom_id = fields.Many2one("uom.uom", string="UdM")
    quantity = fields.Float(string="Cantidad", digits=(16, 4))

    _sql_constraints = [
        ("op_line_plan_unique", "unique(order_id, plan_line_id)",
         "Una tarea planificada no puede repetirse en la misma OP."),
        ("op_line_application_unique", "unique(order_id, program_application_id)",
         "Una aplicación de programa no puede repetirse en la misma OP."),
        ("op_line_harvest_unique", "unique(order_id, harvest_plan_line_id)",
         "Una línea de cosecha no puede repetirse en la misma OP."),
    ]

    @api.constrains(
        "source_type", "plan_line_id", "program_application_id", "harvest_plan_line_id",
    )
    def _check_source_exclusive(self):
        for line in self:
            sources = {
                "plan_line": line.plan_line_id,
                "program_application": line.program_application_id,
                "harvest_line": line.harvest_plan_line_id,
            }
            if not sources.get(line.source_type):
                raise ValidationError(_(
                    "Falta la fuente de origen (%s) de la línea."
                ) % dict(line._fields["source_type"].selection)[line.source_type])
            filled = [key for key, value in sources.items() if value]
            if len(filled) > 1:
                raise ValidationError(_(
                    "Una línea de la OP no puede tener dos fuentes a la vez."
                ))

    def _assert_order_editable(self):
        frozen = self.filtered(lambda line: line.order_id.state in FROZEN_STATES)
        if frozen:
            raise UserError(_(
                "Las líneas de una OP autorizada/reemplazada son inmutables."
            ))

    @api.model_create_multi
    def create(self, vals_list):
        orders = self.env["step.management.production.order"].browse([
            vals.get("order_id") for vals in vals_list if vals.get("order_id")
        ])
        if any(order.state in FROZEN_STATES for order in orders):
            raise UserError(_(
                "No puede agregar líneas a una OP autorizada/reemplazada."
            ))
        return super().create(vals_list)

    def write(self, vals):
        self._assert_order_editable()
        return super().write(vals)

    def unlink(self):
        self._assert_order_editable()
        return super().unlink()
