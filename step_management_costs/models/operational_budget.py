import hashlib
import json
import re
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare

from .budget_template import MONTH_FIELDS
from .exchange_rate import default_conversion_currency

APPROVER_GROUP = "step_management_costs.group_management_approver"
MANAGER_GROUP = "step_management_costs.group_management_manager"

# Campos de cabecera que quedan congelados en un presupuesto aprobado/cerrado/
# reemplazado. El detalle (centros, líneas, meses) se protege además en los
# modelos hijos y por el bloqueo de los One2many.
PROTECTED_HEADER_FIELDS = {
    "description", "company_id", "currency_id", "conversion_currency_id",
    "conversion_rate_type", "date", "season", "template_id", "responsible_id",
    "allocation_ids", "line_ids", "budget_type", "budget_version", "notes",
}
FROZEN_STATES = ("approved", "closed", "superseded")

# Campos de `step.management.budget.line` que se copian al crear una nueva
# revisión (`_revision_line_commands`). Un puente que agregue campos a este
# modelo (p. ej. maquinaria: `machinery_vehicle_id`) debe sumarlos aquí con
# `REVISION_LINE_FIELDS.update({...})` a nivel de módulo — igual criterio
# que `PROTECTED_LINE_FIELDS` en `crop_program.py`/`estimation.py` — para
# que la revisión no los pierda silenciosamente. `month_ids` se maneja
# aparte (con su propio conjunto fijo, ninguna extensión lo toca todavía).
REVISION_LINE_FIELDS = {
    "center_id", "template_line_id", "category", "group_id", "indicator",
    "activity", "product_id", "uom_id", "hectares", "quantity_per_ha",
    "quantity", "unit_price", "calculation_mode", "direct_amount",
}


MONTH_SELECTION = [
    ("may", "Mayo"), ("jun", "Junio"), ("jul", "Julio"), ("aug", "Agosto"),
    ("sep", "Septiembre"), ("oct", "Octubre"), ("nov", "Noviembre"),
    ("dec", "Diciembre"), ("jan", "Enero"), ("feb", "Febrero"),
    ("mar", "Marzo"), ("apr", "Abril"),
]
MONTH_NUMBERS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


class StepManagementOperationalBudget(models.Model):
    _name = "step.management.operational.budget"
    _description = "Presupuesto operacional"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        string="Folio", required=True, copy=False, readonly=True,
        default=lambda self: _("Nuevo"), index=True,
    )
    description = fields.Char(string="Nombre del presupuesto", required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True, default=lambda self: self.env.company,
        index=True, tracking=True,
    )
    currency_id = fields.Many2one(
        "res.currency", string="Moneda", required=True,
        default=lambda self: self.env.company.currency_id,
    )
    conversion_currency_id = fields.Many2one(
        "res.currency", string="Convertir a",
        default=lambda self: default_conversion_currency(self.env),
        domain="[('active', '=', True)]",
    )
    conversion_rate_type = fields.Selection(
        [("estimated", "Estimado mensual"), ("actual", "Real Odoo")],
        string="Tipo de conversión", default="estimated", required=True,
    )
    conversion_available = fields.Boolean(compute="_compute_conversion")
    conversion_factor = fields.Float(
        string="Factor origen → destino", compute="_compute_conversion", digits=(16, 10)
    )
    conversion_target_value = fields.Float(
        string="Valor moneda destino", compute="_compute_conversion", digits=(16, 6)
    )
    date = fields.Date(string="Fecha", required=True, default=fields.Date.context_today, tracking=True)
    season = fields.Char(string="Temporada", required=True, tracking=True, help="Ej.: 2026/2027")
    budget_version = fields.Char(
        string="Versión de presupuesto", tracking=True, copy=False,
        help="Identificador de versión del formato de carga (Anexo 1.6.2.1). "
             "Distinto de la revisión interna del documento.",
    )
    template_id = fields.Many2one(
        "step.management.budget.template", string="Plantilla", tracking=True,
        check_company=True,
        domain="[('company_id', '=', company_id), ('state', '=', 'active')]",
        help="Origen por plantilla. Un presupuesto también puede originarse "
             "desde una carga Excel o construirse a mano.",
    )
    import_id = fields.Many2one(
        "step.management.budget.import", string="Carga de origen", readonly=True, copy=False,
    )
    origin_type = fields.Selection(
        [("template", "Plantilla"), ("import", "Carga Excel"), ("manual", "Manual")],
        string="Origen", compute="_compute_origin_type", store=True,
    )
    budget_type = fields.Selection(
        [("agricultural", "Agrícola (por hectárea)"),
         ("general", "General (formulario libre)")],
        string="Tipo de presupuesto", default="agricultural", required=True,
        tracking=True, copy=True,
        help="«Agrícola»: se calcula desde una plantilla por hectárea y se "
             "extrapola a centros con superficie. «General»: centros no "
             "agrícolas, líneas y montos capturados a mano, sin plantilla ni "
             "escala por hectárea.",
    )
    responsible_id = fields.Many2one(
        "res.users", string="Responsable", required=True, default=lambda self: self.env.user, tracking=True
    )
    allocation_ids = fields.One2many(
        "step.management.budget.center", "budget_id", string="Centros de costo seleccionados", copy=True
    )
    line_ids = fields.One2many(
        "step.management.budget.line", "budget_id", string="Detalle extrapolado", copy=False
    )
    total_hectares = fields.Float(
        string="Hectáreas presupuestadas", compute="_compute_totals", store=True, digits=(16, 4)
    )
    total_amount = fields.Monetary(
        string="Costo presupuestado", compute="_compute_totals", store=True, currency_field="currency_id",
        help="Suma de las líneas de costo. Los ingresos no se incluyen aquí.",
    )
    total_income = fields.Monetary(
        string="Ingreso presupuestado", compute="_compute_totals", store=True,
        currency_field="currency_id",
    )
    margin = fields.Monetary(
        string="Margen presupuestado", compute="_compute_totals", store=True,
        currency_field="currency_id", help="Ingreso presupuestado menos costo presupuestado.",
    )
    cost_per_ha = fields.Monetary(
        string="Costo promedio por hectárea", compute="_compute_totals", store=True,
        currency_field="currency_id",
    )
    total_amount_converted = fields.Monetary(
        string="Presupuesto convertido", compute="_compute_conversion",
        currency_field="conversion_currency_id",
    )
    cost_per_ha_converted = fields.Monetary(
        string="Costo/ha convertido", compute="_compute_conversion",
        currency_field="conversion_currency_id",
    )
    line_count = fields.Integer(string="Líneas", compute="_compute_totals", store=True)
    incomplete_line_count = fields.Integer(
        string="Líneas con distribución incompleta", compute="_compute_incomplete_line_count",
    )
    state = fields.Selection(
        [("draft", "Borrador"), ("calculated", "Calculado"),
         ("approved", "Aprobado"), ("closed", "Cerrado"),
         ("superseded", "Reemplazado"), ("cancelled", "Cancelado")],
        string="Estado", default="draft", required=True, tracking=True, index=True,
    )
    notes = fields.Html(string="Notas y supuestos")
    active = fields.Boolean(default=True)

    approved_by_id = fields.Many2one(
        "res.users", string="Aprobado por", readonly=True, copy=False, tracking=True
    )
    approved_at = fields.Datetime(string="Fecha de aprobación", readonly=True, copy=False, tracking=True)
    revision = fields.Integer(string="Revisión", default=1, copy=False, tracking=True)
    revision_of_id = fields.Many2one(
        "step.management.operational.budget", string="Revisión de", copy=False,
        ondelete="set null", readonly=True,
    )
    superseded_by_id = fields.Many2one(
        "step.management.operational.budget", string="Reemplazado por", copy=False,
        ondelete="set null", readonly=True,
    )
    reopen_reason = fields.Text(string="Motivo de la última reapertura", copy=False, readonly=True)
    approval_snapshot = fields.Text(
        string="Snapshot de aprobación", copy=False, readonly=True,
        help="Copia congelada (JSON) de líneas, cantidades, moneda y tipo de "
             "cambio en el momento de aprobar. Reproduce el cálculo aprobado.",
    )
    approval_hash = fields.Char(
        string="Hash del snapshot", size=64, copy=False, readonly=True,
        help="SHA-256 del snapshot de aprobación.",
    )

    @api.depends("allocation_ids.hectares", "line_ids.amount", "line_ids.flow_type")
    def _compute_totals(self):
        for record in self:
            record.total_hectares = sum(record.allocation_ids.mapped("hectares"))
            cost_lines = record.line_ids.filtered(lambda line: line.flow_type != "income")
            income_lines = record.line_ids.filtered(lambda line: line.flow_type == "income")
            record.total_amount = sum(cost_lines.mapped("amount"))
            record.total_income = sum(income_lines.mapped("amount"))
            record.margin = record.total_income - record.total_amount
            record.cost_per_ha = record.total_amount / record.total_hectares if record.total_hectares else 0.0
            record.line_count = len(record.line_ids)

    @api.depends("line_ids.distribution_complete")
    def _compute_incomplete_line_count(self):
        for record in self:
            record.incomplete_line_count = len(record._incomplete_distribution_lines())

    @api.depends("template_id", "import_id")
    def _compute_origin_type(self):
        for record in self:
            if record.import_id:
                record.origin_type = "import"
            elif record.template_id:
                record.origin_type = "template"
            else:
                record.origin_type = "manual"

    @api.constrains("budget_type", "template_id", "import_id")
    def _check_budget_type_consistency(self):
        for record in self:
            if record.budget_type == "general" and (record.template_id or record.import_id):
                raise ValidationError(_(
                    "Un presupuesto «general» se construye a mano: no puede "
                    "tener plantilla ni carga Excel asociada. Quítelas o "
                    "cámbielo a tipo «agrícola»."
                ))

    @api.depends(
        "total_amount", "cost_per_ha", "currency_id", "conversion_currency_id",
        "conversion_rate_type", "date", "company_id",
    )
    def _compute_conversion(self):
        service = self.env["step.management.exchange.rate"]
        for record in self:
            total_result = service.get_conversion(
                record.total_amount, record.currency_id, record.conversion_currency_id,
                record.company_id, record.date, record.conversion_rate_type,
            )
            hectare_result = service.get_conversion(
                record.cost_per_ha, record.currency_id, record.conversion_currency_id,
                record.company_id, record.date, record.conversion_rate_type,
            )
            record.conversion_available = total_result["available"]
            record.conversion_factor = total_result["factor"]
            record.conversion_target_value = total_result["target_value"]
            record.total_amount_converted = total_result["amount"]
            record.cost_per_ha_converted = hectare_result["amount"]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "step.management.operational.budget"
                ) or _("Nuevo")
        return super().create(vals_list)

    @api.onchange("template_id")
    def _onchange_template_id(self):
        if self.template_id:
            self.currency_id = self.template_id.currency_id
            self.conversion_currency_id = self.template_id.conversion_currency_id
            self.conversion_rate_type = self.template_id.conversion_rate_type

    def action_generate_lines(self):
        for budget in self:
            if budget.state not in ("draft", "calculated"):
                raise UserError("Sólo puede recalcular un presupuesto en borrador o calculado.")
            if budget.budget_type == "general":
                raise UserError(_(
                    "Un presupuesto general se construye a mano: agregue los "
                    "centros y las líneas de detalle directamente. No usa "
                    "plantilla por hectárea."
                ))
            if budget.import_id:
                raise UserError(_(
                    "Este presupuesto proviene de una carga Excel. Edítelo desde "
                    "el detalle o reabra una nueva carga."
                ))
            if not budget.template_id:
                raise UserError(_("Seleccione una plantilla para calcular el presupuesto."))
            if not budget.template_id.line_ids:
                raise UserError("La plantilla no contiene indicadores.")
            if not budget.allocation_ids:
                raise UserError("Seleccione al menos un centro de costo.")
            invalid = budget.allocation_ids.filtered(lambda allocation: allocation.hectares <= 0)
            if invalid:
                raise UserError("Todos los centros seleccionados deben tener hectáreas mayores que cero.")

            budget.line_ids.unlink()
            commands = []
            base_hectares = budget.template_id.base_hectares
            for allocation in budget.allocation_ids:
                scale = allocation.hectares / base_hectares
                for template_line in budget.template_id.line_ids:
                    month_commands = []
                    for month in MONTH_FIELDS:
                        template_quantity = template_line[month] or 0.0
                        if template_quantity:
                            month_commands.append((0, 0, {
                                "month": month,
                                "quantity": template_quantity * scale,
                                "unit_price": template_line.unit_price,
                            }))
                    commands.append((0, 0, {
                        "center_id": allocation.center_id.id,
                        "template_line_id": template_line.id,
                        "category": template_line.category,
                        "group_id": template_line.group_id.id,
                        "indicator": template_line.indicator,
                        "activity": template_line.activity,
                        "product_id": template_line.product_id.id,
                        "uom_id": template_line.uom_id.id,
                        "hectares": allocation.hectares,
                        "quantity_per_ha": template_line.quantity_per_ha,
                        "quantity": template_line.quantity_per_ha * allocation.hectares,
                        "unit_price": template_line.unit_price,
                        "calculation_mode": "quantity",
                        "month_ids": month_commands,
                    }))
            budget.write({"line_ids": commands, "state": "calculated"})
            budget.message_post(
                body=_("Presupuesto generado desde la plantilla %s para %s centro(s) y %.2f hectáreas.")
                % (budget.template_id.display_name, len(budget.allocation_ids), budget.total_hectares)
            )

    # ------------------------------------------------------------------
    # Comprobaciones de rol y transición (válidas también por RPC)
    # ------------------------------------------------------------------
    def _ensure_approver(self):
        if not self.env.user.has_group(APPROVER_GROUP):
            raise UserError(_(
                "Necesita el perfil «Aprobador / Control» de Gestión y Costos "
                "para esta acción."
            ))

    def _ensure_transition(self, allowed_states, action_label):
        wrong = self.filtered(lambda record: record.state not in allowed_states)
        if wrong:
            raise UserError(_(
                "No se puede %(action)s el presupuesto %(names)s en estado "
                "«%(state)s»."
            ) % {
                "action": action_label,
                "names": ", ".join(wrong.mapped("name")),
                "state": ", ".join(sorted(set(wrong.mapped("state")))),
            })

    def _incomplete_distribution_lines(self):
        return self.line_ids.filtered(lambda line: not line.distribution_complete)

    def _centers_without_analytic(self):
        problems = self.env["step.management.cost.center"]
        centers = self.allocation_ids.center_id | self.line_ids.center_id
        for center in centers:
            account = center.analytic_account_id
            if not account or (account.company_id and account.company_id != self.company_id):
                problems |= center
        return problems

    def _duplicate_analytic_centers(self):
        """Return center groups that share one analytic account in this budget."""
        self.ensure_one()
        by_account = {}
        centers = self.allocation_ids.center_id | self.line_ids.center_id
        for center in centers.filtered("analytic_account_id"):
            by_account.setdefault(center.analytic_account_id.id, self.env[center._name])
            by_account[center.analytic_account_id.id] |= center
        return [group for group in by_account.values() if len(group) > 1]

    def _line_centers_outside_allocations(self):
        self.ensure_one()
        return self.line_ids.center_id - self.allocation_ids.center_id

    def _check_segregation(self):
        param = self.env["ir.config_parameter"].sudo().get_param(
            "step_management_costs.enforce_segregation", "0"
        )
        if param not in ("1", "true", "True"):
            return
        if self.env.user.has_group(MANAGER_GROUP):
            return
        if self.create_uid and self.create_uid == self.env.user:
            raise UserError(_(
                "Segregación de funciones: quien crea un presupuesto no puede "
                "aprobarlo. Solicite la aprobación a otro usuario o a un "
                "administrador."
            ))

    # ------------------------------------------------------------------
    # Snapshot reproducible del aprobado
    # ------------------------------------------------------------------
    def _build_approval_snapshot(self):
        self.ensure_one()
        lines = []
        for line in self.line_ids.sorted(key=lambda l: (l.center_id.id, l.group_id.id, l.id)):
            lines.append({
                "center": line.center_id.code or line.center_id.display_name,
                "group": line.group_id.code or line.group_id.display_name,
                "flow_type": line.flow_type or "cost",
                "category": line.category,
                "indicator": line.indicator,
                "uom": line.uom_id.name or "",
                "hectares": round(line.hectares, 4),
                "quantity": round(line.quantity, 4),
                "unit_price": round(line.unit_price, 6),
                "calculation_mode": line.calculation_mode,
                "direct_amount": round(line.direct_amount, 2),
                "amount": round(line.amount, 2),
                "monthly_amount": round(line.monthly_amount, 2),
                "months": [
                    {"month": month.month, "quantity": round(month.quantity, 4),
                     "unit_price": round(month.unit_price, 6),
                     "direct_amount": round(month.direct_amount, 2),
                     "amount": round(month.amount, 2),
                     "conversion_date": fields.Date.to_string(month.conversion_date),
                     "amount_converted": round(month.amount_converted or 0.0, 2)}
                    for month in line.month_ids.sorted(key=lambda m: m.month or "")
                ],
            })
        payload = {
            "budget": self.name,
            "revision": self.revision,
            "season": self.season,
            "currency": self.currency_id.name,
            "conversion_currency": self.conversion_currency_id.name or "",
            "conversion_rate_type": self.conversion_rate_type,
            "conversion_factor": round(self.conversion_factor or 0.0, 10),
            "conversion_target_value": round(self.conversion_target_value or 0.0, 6),
            "total_hectares": round(self.total_hectares, 4),
            "total_amount": round(self.total_amount, 2),
            "total_income": round(self.total_income, 2),
            "margin": round(self.margin, 2),
            "total_amount_converted": round(self.total_amount_converted or 0.0, 2),
            "lines": lines,
        }
        return json.dumps(payload, sort_keys=True, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Acciones de estado
    # ------------------------------------------------------------------
    def action_approve(self):
        self._ensure_approver()
        self._ensure_transition(("calculated",), _("aprobar"))
        for record in self:
            origin = record.revision_of_id
            if origin and origin.state not in ("approved", "closed"):
                raise UserError(_(
                    "La versión de origen %(origin)s ya no está vigente para ser "
                    "reemplazada (estado: %(state)s)."
                ) % {"origin": origin.display_name, "state": origin.state})
            if not record.line_ids:
                raise UserError(_("Genere el detalle antes de aprobar el presupuesto."))
            incomplete = record._incomplete_distribution_lines()
            if incomplete:
                raise UserError(_(
                    "La distribución mensual está incompleta en %(count)s línea(s). "
                    "Complete el 100%% de las cantidades antes de aprobar:\n%(detail)s"
                ) % {
                    "count": len(incomplete),
                    "detail": "\n".join(
                        "· %s / %s / %s" % (l.center_id.display_name, l.group_id.display_name, l.indicator)
                        for l in incomplete[:20]
                    ),
                })
            missing = record._centers_without_analytic()
            if missing:
                raise UserError(_(
                    "Los siguientes centros de costo no tienen una cuenta "
                    "analítica de la empresa %(company)s y no pueden aprobarse:\n%(detail)s"
                ) % {
                    "company": record.company_id.display_name,
                    "detail": "\n".join("· %s" % c.display_name for c in missing),
                })
            outside = record._line_centers_outside_allocations()
            if outside:
                raise UserError(_(
                    "Las líneas usan centros que no están en la pestaña «Centros "
                    "de costo»: %(centers)s. Agréguelos antes de aprobar."
                ) % {"centers": ", ".join(outside.mapped("display_name"))})
            duplicates = record._duplicate_analytic_centers()
            if duplicates:
                detail = "; ".join(
                    "%s → %s" % (
                        group[0].analytic_account_id.display_name,
                        ", ".join(group.mapped("display_name")),
                    )
                    for group in duplicates
                )
                raise UserError(_(
                    "No se puede atribuir el gasto real: una misma cuenta analítica "
                    "está vinculada a más de un centro del presupuesto: %s"
                ) % detail)
            record._check_segregation()
            snapshot = record._build_approval_snapshot()
            record.write({
                "state": "approved",
                "approved_by_id": self.env.user.id,
                "approved_at": fields.Datetime.now(),
                "approval_snapshot": snapshot,
                "approval_hash": hashlib.sha256(snapshot.encode("utf-8")).hexdigest(),
            })
            record.message_post(body=_(
                "Presupuesto aprobado por %s. Snapshot congelado (hash %s…)."
            ) % (self.env.user.display_name, record.approval_hash[:12]))
            if origin and origin.state in ("approved", "closed"):
                origin.write({
                    "state": "superseded",
                    "superseded_by_id": record.id,
                })
                origin.message_post(body=_(
                    "Reemplazado por la revisión %s (%s)."
                ) % (record.revision, record.name))

    def action_close(self):
        self._ensure_approver()
        self._ensure_transition(("approved",), _("cerrar"))
        self.write({"state": "closed"})

    def action_cancel(self):
        # Un presupuesto aprobado no se cancela en silencio: primero se reabre
        # (con motivo) y luego se cancela desde borrador.
        self._ensure_transition(("draft", "calculated"), _("cancelar"))
        self.write({"state": "cancelled"})

    def action_set_draft(self):
        self._ensure_transition(("calculated", "cancelled"), _("volver a borrador"))
        self.write({"state": "draft"})

    def action_prepare_general(self):
        """Validate a manual general budget and make it ready for approval."""
        self._ensure_transition(("draft", "calculated"), _("validar"))
        for record in self:
            if record.budget_type != "general":
                raise UserError(_(
                    "Esta acción sólo corresponde a presupuestos generales."
                ))
            if not record.line_ids:
                raise UserError(_("Agregue al menos una línea de presupuesto."))
            if record._line_centers_outside_allocations():
                raise UserError(_(
                    "Todas las líneas deben usar centros incluidos en la pestaña "
                    "«Centros de costo»."
                ))
            if record._incomplete_distribution_lines():
                raise UserError(_(
                    "Complete y concilie la distribución mensual de todas las "
                    "líneas antes de validar."
                ))
            record.write({"state": "calculated"})

    def action_reopen(self):
        """Open the wizard that creates a traceable corrective revision."""
        self.ensure_one()
        self._ensure_approver()
        self._ensure_transition(("approved",), _("reabrir"))
        return {
            "type": "ir.actions.act_window",
            "name": _("Crear corrección presupuestaria"),
            "res_model": "step.management.budget.reopen.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_budget_id": self.id},
        }

    def _revision_line_commands(self):
        self.ensure_one()
        commands = []
        for line in self.line_ids:
            vals = {}
            for field_name in REVISION_LINE_FIELDS:
                if field_name not in line._fields:
                    continue  # campo de un puente no instalado en este entorno
                value = line[field_name]
                vals[field_name] = value.id if isinstance(value, models.BaseModel) else value
            vals["month_ids"] = [(0, 0, {
                "month": month.month,
                "quantity": month.quantity,
                "unit_price": month.unit_price,
                "direct_amount": month.direct_amount,
            }) for month in line.month_ids]
            commands.append((0, 0, vals))
        return commands

    def _create_revision(self, reason=None):
        self.ensure_one()
        self._ensure_approver()
        self._ensure_transition(("approved", "closed"), _("crear una nueva revisión de"))
        existing = self.search([
            ("revision_of_id", "=", self.id),
            ("state", "not in", ("cancelled", "superseded")),
        ], limit=1)
        if existing:
            raise UserError(_(
                "Ya existe la revisión sucesora %(name)s en estado %(state)s. "
                "Continúe o cancele esa revisión antes de crear otra."
            ) % {"name": existing.display_name, "state": existing.state})
        children = self.search([("revision_of_id", "=", self.id)])
        next_revision = max(children.mapped("revision") or [self.revision]) + 1
        values = {
            "revision": next_revision,
            "revision_of_id": self.id,
            "state": "draft",
            "description": "%s (rev. %s)" % (self.description, next_revision),
            "import_id": self.import_id.id,
            "line_ids": self._revision_line_commands(),
        }
        if reason:
            values["reopen_reason"] = reason.strip()
        revision = self.copy(values)
        self.message_post(body=_(
            "Se creó la revisión %(revision)s: %(name)s. El presupuesto actual "
            "permanece inmutable y vigente hasta que la nueva revisión sea aprobada."
        ) % {"revision": revision.revision, "name": revision.name})
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
            "res_model": "step.management.operational.budget",
            "res_id": revision.id,
            "view_mode": "form",
            "target": "current",
        }

    # ------------------------------------------------------------------
    # Inmutabilidad del aprobado
    # ------------------------------------------------------------------
    def write(self, vals):
        touched = PROTECTED_HEADER_FIELDS & set(vals)
        if touched:
            frozen = self.filtered(lambda record: record.state in FROZEN_STATES)
            if frozen:
                raise UserError(_(
                    "El presupuesto %(names)s está aprobado/cerrado y no "
                    "admite cambios en: %(fields)s. Cree una nueva revisión."
                ) % {
                    "names": ", ".join(frozen.mapped("name")),
                    "fields": ", ".join(sorted(touched)),
                })
        return super().write(vals)

    def unlink(self):
        blocked = self.filtered(lambda record: record.state != "draft")
        if blocked and not self.env.user.has_group(MANAGER_GROUP):
            raise UserError(_(
                "Sólo un administrador puede eliminar presupuestos que no estén "
                "en borrador: %s"
            ) % ", ".join(blocked.mapped("name")))
        frozen = self.filtered(lambda record: record.state in FROZEN_STATES)
        if frozen:
            raise UserError(_(
                "No se puede eliminar un presupuesto aprobado/cerrado/reemplazado "
                "(%s). Su trazabilidad debe conservarse."
            ) % ", ".join(frozen.mapped("name")))
        return super().unlink()


class StepManagementBudgetCenter(models.Model):
    _name = "step.management.budget.center"
    _description = "Centro incluido en presupuesto"
    _order = "center_id"
    _check_company_auto = True

    budget_id = fields.Many2one(
        "step.management.operational.budget", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        related="budget_id.company_id", string="Empresa", store=True, index=True,
    )
    center_id = fields.Many2one(
        "step.management.cost.center", string="Centro de costo", required=True,
        check_company=True,
        domain="[('company_id', '=', parent.company_id)]",
    )
    registered_hectares = fields.Float(
        related="center_id.hectares", string="Hectáreas registradas", readonly=True
    )
    hectares = fields.Float(string="Hectáreas a presupuestar", required=True, digits=(16, 4))
    notes = fields.Char(string="Observación")

    _sql_constraints = [
        ("budget_center_uniq", "unique(budget_id, center_id)",
         "No puede seleccionar dos veces el mismo centro de costo en un presupuesto."),
    ]

    @api.onchange("center_id")
    def _onchange_center_id(self):
        if self.center_id:
            self.hectares = self.center_id.hectares

    @api.constrains("hectares", "budget_id")
    def _check_hectares(self):
        for record in self:
            if record.hectares < 0:
                raise ValidationError(_(
                    "Las hectáreas a presupuestar no pueden ser negativas."
                ))
            if record.budget_id.budget_type != "general" and record.hectares <= 0:
                raise ValidationError(_(
                    "Las hectáreas a presupuestar deben ser mayores que cero "
                    "en un presupuesto agrícola."
                ))


class StepManagementBudgetLine(models.Model):
    _name = "step.management.budget.line"
    _description = "Línea de presupuesto extrapolada"
    _order = "center_id, group_id, category, id"
    _check_company_auto = True

    budget_id = fields.Many2one(
        "step.management.operational.budget", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(related="budget_id.company_id", store=True, index=True)
    currency_id = fields.Many2one(related="budget_id.currency_id", store=True)
    conversion_currency_id = fields.Many2one(related="budget_id.conversion_currency_id")
    conversion_rate_type = fields.Selection(related="budget_id.conversion_rate_type")
    conversion_date = fields.Date(related="budget_id.date")
    center_id = fields.Many2one(
        "step.management.cost.center", string="Centro de costo", required=True,
        index=True, check_company=True,
    )
    template_line_id = fields.Many2one(
        "step.management.budget.template.line", string="Indicador de origen",
        ondelete="restrict", check_company=True,
    )
    category = fields.Selection(
        [("labor", "Mano de obra"), ("input", "Insumo agrícola"),
         ("machinery", "Maquinaria"), ("service", "Servicio"), ("other", "Otro")],
        required=True, string="Categoría", index=True,
    )
    group_id = fields.Many2one(
        "step.management.budget.group", string="Grupo", required=True, index=True,
        check_company=True,
    )
    flow_type = fields.Selection(
        related="group_id.flow_type", string="Naturaleza", store=True, index=True,
    )
    indicator = fields.Char(string="Indicador / labor", required=True)
    activity = fields.Char(string="Actividad")
    product_id = fields.Many2one("product.product", string="Producto")
    uom_id = fields.Many2one("uom.uom", string="UdM")
    hectares = fields.Float(
        string="Hectáreas", digits=(16, 4),
        help="Requerida en presupuestos agrícolas (escala por hectárea). "
             "En un presupuesto general puede quedar en cero.",
    )
    quantity_per_ha = fields.Float(string="Cantidad/ha", digits=(16, 4))
    quantity = fields.Float(string="Cantidad total", digits=(16, 4))
    unit_price = fields.Monetary(string="Tarifa", currency_field="currency_id")
    calculation_mode = fields.Selection(
        [("quantity", "Cantidad × tarifa"), ("direct", "Monto directo")],
        string="Modo de cálculo", default="quantity", required=True,
        help="Use «Monto directo» en presupuestos generales cuando no exista "
             "cantidad o tarifa aplicable.",
    )
    direct_amount = fields.Monetary(
        string="Monto directo", currency_field="currency_id",
        help="Monto total de la línea cuando el modo de cálculo es directo.",
    )
    amount = fields.Monetary(
        string="Total", compute="_compute_amount", store=True, currency_field="currency_id"
    )
    unit_price_converted = fields.Monetary(
        string="Tarifa convertida", compute="_compute_conversion",
        currency_field="conversion_currency_id",
    )
    amount_converted = fields.Monetary(
        string="Total convertido", compute="_compute_conversion",
        currency_field="conversion_currency_id",
    )
    month_ids = fields.One2many("step.management.budget.month", "budget_line_id", string="Distribución mensual")
    monthly_quantity = fields.Float(
        string="Cantidad distribuida", compute="_compute_distribution", store=True, digits=(16, 4),
    )
    monthly_amount = fields.Monetary(
        string="Monto distribuido", compute="_compute_distribution", store=True,
        currency_field="currency_id",
    )
    distribution_complete = fields.Boolean(
        string="Distribución mensual completa", compute="_compute_distribution", store=True,
        help="Verdadero cuando la línea tiene distribución mensual y su suma "
             "coincide con la cantidad total dentro de la tolerancia de la UdM. "
             "Un presupuesto no puede aprobarse con líneas incompletas.",
    )

    @api.depends("quantity", "unit_price", "calculation_mode", "direct_amount")
    def _compute_amount(self):
        for record in self:
            record.amount = (
                record.direct_amount if record.calculation_mode == "direct"
                else record.quantity * record.unit_price
            )

    @api.depends(
        "month_ids.quantity", "month_ids.amount", "quantity", "amount",
        "calculation_mode", "uom_id.rounding", "currency_id.rounding",
    )
    def _compute_distribution(self):
        for record in self:
            months = record.month_ids
            record.monthly_quantity = sum(months.mapped("quantity"))
            record.monthly_amount = sum(months.mapped("amount"))
            if not months:
                record.distribution_complete = False
                continue
            amount_ok = float_compare(
                record.monthly_amount, record.amount,
                precision_rounding=record.currency_id.rounding or 0.01,
            ) == 0
            if record.calculation_mode == "direct":
                record.distribution_complete = amount_ok
            else:
                quantity_ok = float_compare(
                    record.monthly_quantity, record.quantity,
                    precision_rounding=record.uom_id.rounding or 0.0001,
                ) == 0
                record.distribution_complete = quantity_ok and amount_ok

    @api.constrains("hectares", "budget_id", "calculation_mode")
    def _check_line_hectares(self):
        for record in self:
            if record.hectares and record.hectares < 0:
                raise ValidationError(_(
                    "Las hectáreas de la línea «%s» no pueden ser negativas."
                ) % (record.indicator or record.id))
            if record.budget_id.budget_type != "general" and not record.hectares:
                raise ValidationError(_(
                    "Las líneas de un presupuesto agrícola requieren hectáreas. "
                    "Revise la línea «%s»."
                ) % (record.indicator or record.id))
            if (
                record.budget_id.budget_type != "general"
                and record.calculation_mode == "direct"
            ):
                raise ValidationError(_(
                    "El modo «Monto directo» sólo está disponible para "
                    "presupuestos generales."
                ))

    @api.constrains(
        "month_ids", "quantity", "uom_id", "unit_price", "direct_amount",
        "calculation_mode",
    )
    def _check_monthly_distribution(self):
        for record in self:
            if not record.month_ids:
                continue
            monthly_amount = sum(record.month_ids.mapped("amount"))
            amount_mismatch = float_compare(
                monthly_amount, record.amount,
                precision_rounding=record.currency_id.rounding or 0.01,
            ) != 0
            quantity_mismatch = False
            if record.calculation_mode != "direct":
                quantity_mismatch = float_compare(
                    sum(record.month_ids.mapped("quantity")), record.quantity,
                    precision_rounding=record.uom_id.rounding or 0.0001,
                ) != 0
            if quantity_mismatch or amount_mismatch:
                raise ValidationError(_(
                    "La distribución mensual de «%(indicator)s» (centro %(center)s) "
                    "no concilia con el total. Cantidad mensual/total: "
                    "%(months_qty).4f / %(total_qty).4f; monto mensual/total: "
                    "%(months_amount).2f / %(total_amount).2f."
                ) % {
                    "indicator": record.indicator,
                    "center": record.center_id.display_name,
                    "months_qty": sum(record.month_ids.mapped("quantity")),
                    "total_qty": record.quantity,
                    "months_amount": monthly_amount,
                    "total_amount": record.amount,
                })

    def unlink(self):
        frozen = self.filtered(lambda line: line.budget_id.state in FROZEN_STATES)
        if frozen:
            raise UserError(_(
                "No se puede eliminar detalle de un presupuesto aprobado/cerrado/"
                "reemplazado. Cree una nueva revisión."
            ))
        return super().unlink()

    def write(self, vals):
        protected = {"quantity", "unit_price", "hectares", "quantity_per_ha",
                     "center_id", "group_id", "category", "month_ids",
                     "calculation_mode", "direct_amount", "indicator", "activity",
                     "product_id", "uom_id"} & set(vals)
        if protected:
            frozen = self.filtered(lambda line: line.budget_id.state in FROZEN_STATES)
            if frozen:
                raise UserError(_(
                    "El detalle del presupuesto %s está congelado. Cree una "
                    "nueva revisión."
                ) % ", ".join(frozen.mapped("budget_id.name")))
        return super().write(vals)

    @api.depends(
        "unit_price", "amount", "currency_id", "conversion_currency_id",
        "conversion_rate_type", "conversion_date", "company_id",
    )
    def _compute_conversion(self):
        service = self.env["step.management.exchange.rate"]
        for record in self:
            unit_result = service.get_conversion(
                record.unit_price, record.currency_id, record.conversion_currency_id,
                record.company_id, record.conversion_date, record.conversion_rate_type,
            )
            amount_result = service.get_conversion(
                record.amount, record.currency_id, record.conversion_currency_id,
                record.company_id, record.conversion_date, record.conversion_rate_type,
            )
            record.unit_price_converted = unit_result["amount"]
            record.amount_converted = amount_result["amount"]


class StepManagementBudgetMonth(models.Model):
    _name = "step.management.budget.month"
    _description = "Distribución mensual de presupuesto"
    _order = "month, id"
    _check_company_auto = True

    budget_line_id = fields.Many2one("step.management.budget.line", required=True, ondelete="cascade", index=True)
    budget_id = fields.Many2one(related="budget_line_id.budget_id", store=True, index=True)
    center_id = fields.Many2one(related="budget_line_id.center_id", store=True, index=True)
    group_id = fields.Many2one(related="budget_line_id.group_id", store=True, index=True)
    currency_id = fields.Many2one(related="budget_line_id.currency_id", store=True)
    company_id = fields.Many2one(related="budget_line_id.company_id")
    conversion_currency_id = fields.Many2one(related="budget_line_id.conversion_currency_id")
    conversion_rate_type = fields.Selection(related="budget_line_id.conversion_rate_type")
    conversion_date = fields.Date(string="Mes de conversión", compute="_compute_conversion_date")
    month = fields.Selection(MONTH_SELECTION, string="Mes", required=True, index=True)
    quantity = fields.Float(string="Cantidad", digits=(16, 4))
    unit_price = fields.Monetary(string="Tarifa", currency_field="currency_id")
    direct_amount = fields.Monetary(
        string="Monto directo", currency_field="currency_id",
        help="Se usa cuando la línea padre tiene modo «Monto directo».",
    )
    amount = fields.Monetary(string="Total", compute="_compute_amount", store=True, currency_field="currency_id")
    unit_price_converted = fields.Monetary(
        string="Tarifa convertida", compute="_compute_conversion",
        currency_field="conversion_currency_id",
    )
    amount_converted = fields.Monetary(
        string="Total convertido", compute="_compute_conversion",
        currency_field="conversion_currency_id",
    )

    @api.depends("month", "budget_id.season", "budget_id.date")
    def _compute_conversion_date(self):
        for record in self:
            month_number = MONTH_NUMBERS.get(record.month)
            if not month_number:
                record.conversion_date = record.budget_id.date
                continue
            years = [int(value) for value in re.findall(r"\b\d{4}\b", record.budget_id.season or "")]
            if years:
                year = years[0] if month_number >= 5 else (
                    years[1] if len(years) > 1 else years[0] + 1
                )
            else:
                budget_date = record.budget_id.date or fields.Date.context_today(record)
                year = budget_date.year + (
                    1 if month_number < 5 and budget_date.month >= 5 else 0
                )
            record.conversion_date = date(year, month_number, 1)

    @api.depends(
        "quantity", "unit_price", "direct_amount",
        "budget_line_id.calculation_mode",
    )
    def _compute_amount(self):
        for record in self:
            record.amount = (
                record.direct_amount
                if record.budget_line_id.calculation_mode == "direct"
                else record.quantity * record.unit_price
            )

    @api.constrains("quantity", "unit_price", "direct_amount", "month")
    def _check_parent_distribution(self):
        # Un cambio directo en un mes no dispara el @api.constrains del One2many
        # padre; se revalida explícitamente la cuadratura de la línea.
        for line in self.mapped("budget_line_id"):
            line._check_monthly_distribution()

    @api.constrains("budget_line_id", "month")
    def _check_unique_month(self):
        for record in self:
            if not record.month:
                continue
            duplicate = self.search_count([
                ("budget_line_id", "=", record.budget_line_id.id),
                ("month", "=", record.month),
                ("id", "!=", record.id),
            ])
            if duplicate:
                raise ValidationError(_(
                    "El mes %s está repetido en la distribución de una misma línea."
                ) % dict(MONTH_SELECTION).get(record.month, record.month))

    _sql_constraints = [
        ("budget_line_month_uniq", "unique(budget_line_id, month)",
         "No puede repetir el mismo mes en una línea de presupuesto."),
    ]

    def unlink(self):
        frozen = self.filtered(
            lambda month: month.budget_line_id.budget_id.state in FROZEN_STATES
        )
        if frozen:
            raise UserError(_(
                "No se puede modificar la distribución mensual de un presupuesto "
                "aprobado/cerrado/reemplazado."
            ))
        return super().unlink()

    def write(self, vals):
        if {"quantity", "unit_price", "direct_amount", "month"} & set(vals):
            frozen = self.filtered(
                lambda month: month.budget_line_id.budget_id.state in FROZEN_STATES
            )
            if frozen:
                raise UserError(_(
                    "La distribución mensual del presupuesto está congelada. "
                    "Cree una nueva revisión."
                ))
        return super().write(vals)

    @api.depends(
        "unit_price", "amount", "currency_id", "conversion_currency_id",
        "conversion_rate_type", "conversion_date", "company_id",
    )
    def _compute_conversion(self):
        service = self.env["step.management.exchange.rate"]
        for record in self:
            unit_result = service.get_conversion(
                record.unit_price, record.currency_id, record.conversion_currency_id,
                record.company_id, record.conversion_date, record.conversion_rate_type,
            )
            amount_result = service.get_conversion(
                record.amount, record.currency_id, record.conversion_currency_id,
                record.company_id, record.conversion_date, record.conversion_rate_type,
            )
            record.unit_price_converted = unit_result["amount"]
            record.amount_converted = amount_result["amount"]
