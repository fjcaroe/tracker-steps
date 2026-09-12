import hashlib
import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare

# Estados de presupuesto que sirven como fuente conciliada e inmutable para
# derivar tareas semanales (F4-A4).
BUDGET_SOURCE_STATES = ("approved", "closed", "superseded")


class StepManagementPlan(models.Model):
    _name = "step.management.plan"
    _description = "Plan operacional"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_start desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        string="Folio", required=True, readonly=True, copy=False, default=lambda self: _("Nuevo")
    )
    description = fields.Char(string="Nombre del plan", required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True, tracking=True
    )
    responsible_id = fields.Many2one(
        "res.users", string="Responsable", required=True, default=lambda self: self.env.user, tracking=True
    )
    budget_id = fields.Many2one(
        "step.management.operational.budget", string="Presupuesto relacionado",
        check_company=True,
    )
    season = fields.Char(
        string="Temporada", help="Ej.: 2026/2027. Si se deja vacío se toma del "
        "presupuesto relacionado al generar tareas semanales.",
    )
    source_type = fields.Selection(
        [("manual", "Manual"), ("budget", "Desde presupuesto")],
        string="Origen", default="manual", tracking=True,
    )
    center_ids = fields.Many2many("step.management.cost.center", string="Centros de costo")
    date_start = fields.Date(string="Inicio", required=True, tracking=True)
    date_end = fields.Date(string="Término", required=True, tracking=True)
    week_reference = fields.Char(string="Semana / referencia")
    line_ids = fields.One2many("step.management.plan.line", "plan_id", string="Tareas")
    generated_line_count = fields.Integer(
        string="Tareas generadas", compute="_compute_generated_line_count",
    )
    progress = fields.Float(string="Avance", compute="_compute_progress", store=True)
    state = fields.Selection(
        [("draft", "Borrador"), ("planned", "Planificado"), ("in_progress", "En ejecución"),
         ("done", "Terminado"), ("cancelled", "Cancelado")],
        default="draft", required=True, tracking=True,
    )
    notes = fields.Html(string="Notas")

    @api.depends("line_ids.state")
    def _compute_progress(self):
        for record in self:
            total = len(record.line_ids)
            done = len(record.line_ids.filtered(lambda line: line.state == "done"))
            record.progress = done * 100.0 / total if total else 0.0

    @api.depends("line_ids.generated")
    def _compute_generated_line_count(self):
        for record in self:
            record.generated_line_count = len(
                record.line_ids.filtered("generated")
            )

    # ------------------------------------------------------------------
    # Tareas semanales derivadas del presupuesto aprobado (Fase 4)
    # ------------------------------------------------------------------
    def _build_weekly_task_commands(self):
        """Calcula (sin escribir) los comandos `(0,0,{...})` de tareas
        semanales derivadas del presupuesto aprobado. Devuelve
        `(commands, season)`. Valida presupuesto/temporada/conciliación y
        lanza `UserError` igual que antes; no toca `line_ids`.

        Respuesta del cliente (Corte 1 post Fase 6): antes de borrar/recrear
        las tareas automáticas debe existir una vista previa — este método
        es el cálculo puro que consume tanto el wizard de vista previa como
        la confirmación (`_apply_weekly_task_commands`).

        R1 (revisión post Corte 1): la validación de estado del plan vive
        aquí (no sólo en `action_generate_weekly_tasks`) para que también
        se aplique si el wizard se instancia por RPC directo, saltándose el
        botón del plan."""
        self.ensure_one()
        if self.state not in ("draft", "planned"):
            raise UserError(_(
                "Sólo se pueden (re)generar tareas semanales en un plan en "
                "borrador o planificado."
            ))
        period = self.env["step.management.period.service"]
        budget = self.budget_id
        if not budget:
            raise UserError(_(
                "Seleccione el presupuesto relacionado antes de generar "
                "tareas semanales."
            ))
        if budget.state not in BUDGET_SOURCE_STATES:
            raise UserError(_(
                "El presupuesto %(name)s debe estar aprobado o cerrado para "
                "derivar tareas semanales (estado actual: %(state)s)."
            ) % {"name": budget.name, "state": budget.state})
        if budget.company_id != self.company_id:
            raise UserError(_(
                "El presupuesto relacionado pertenece a otra empresa."
            ))
        season = (self.season or budget.season or "").strip()
        if not season:
            raise UserError(_("No se pudo determinar la temporada."))

        commands = []
        for budget_line in budget.line_ids:
            if not budget_line.month_ids:
                continue
            rounding = budget_line.uom_id.rounding or 0.01
            month_values = {
                month.month: month.quantity for month in budget_line.month_ids
            }
            weeks = period.distribute_monthly_to_weeks(
                season, month_values, rounding=rounding
            )
            distributed = 0.0
            for week in weeks:
                if not week["quantity"]:
                    continue
                distributed += week["quantity"]
                commands.append((0, 0, {
                    "date": week["monday"],
                    "center_id": budget_line.center_id.id,
                    "indicator": budget_line.indicator,
                    "quantity": week["quantity"],
                    "uom_id": budget_line.uom_id.id,
                    "week_label": week["label"],
                    "iso_year": week["iso_year"],
                    "iso_week": week["iso_week"],
                    "generated": True,
                    "budget_line_id": budget_line.id,
                }))
            expected = sum(budget_line.month_ids.mapped("quantity"))
            if float_compare(
                distributed, expected, precision_rounding=rounding
            ) != 0:
                raise UserError(_(
                    "La distribución semanal de «%(indicator)s» (%(center)s) "
                    "suma %(got).4f y no concilia con el presupuesto "
                    "(%(exp).4f)."
                ) % {
                    "indicator": budget_line.indicator,
                    "center": budget_line.center_id.display_name,
                    "got": distributed, "exp": expected,
                })
        return commands, season

    def _weekly_task_fingerprint(self, commands, season):
        """Huella determinista de la fuente y de los comandos mostrados en
        la vista previa (R1). `_build_weekly_task_commands` es una función
        pura de datos ya persistidos (presupuesto/plan/líneas); si la huella
        no cambió, los comandos recalculados son, por construcción,
        idénticos a los que el usuario vio. No hace falta persistir el blob
        completo de comandos para el contrato optimista."""
        payload = {
            "season": season,
            "commands": [vals for (_op, _zero, vals) in commands],
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()

    def _apply_weekly_task_commands(self, commands, season):
        """Aplica los comandos ya calculados: borra las tareas generadas
        anteriores (las manuales nunca se tocan) y crea las nuevas."""
        self.ensure_one()
        self.line_ids.filtered("generated").unlink()
        self.write({
            "line_ids": commands,
            "source_type": "budget",
            "season": season,
        })
        self.message_post(body=_(
            "Generadas %(count)s tarea(s) semanal(es) desde el presupuesto "
            "%(budget)s (vista previa confirmada)."
        ) % {"count": len(commands), "budget": self.budget_id.name})

    def action_generate_weekly_tasks(self):
        """Abre la vista previa de regeneración; no escribe nada todavía."""
        self.ensure_one()
        if self.state not in ("draft", "planned"):
            raise UserError(_(
                "Sólo se pueden (re)generar tareas semanales en un plan en "
                "borrador o planificado."
            ))
        return {
            "type": "ir.actions.act_window",
            "name": _("Vista previa: regenerar tareas semanales"),
            "res_model": "step.management.plan.weekly.preview.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_plan_id": self.id},
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                vals["name"] = self.env["ir.sequence"].next_by_code("step.management.plan") or _("Nuevo")
        return super().create(vals_list)

    @api.constrains("date_start", "date_end")
    def _check_dates(self):
        for record in self:
            if record.date_start and record.date_end and record.date_end < record.date_start:
                raise ValidationError("La fecha de término no puede ser anterior al inicio.")

    @api.constrains("center_ids", "budget_id", "company_id")
    def _check_company_consistency(self):
        # Odoo no valida automáticamente la coherencia de compañía en un
        # Many2many; se hace explícitamente.
        for record in self:
            wrong = record.center_ids.filtered(
                lambda center: center.company_id != record.company_id
            )
            if wrong:
                raise ValidationError(
                    "Los centros de costo %s no pertenecen a la empresa del plan."
                    % ", ".join(wrong.mapped("display_name"))
                )
            if record.budget_id and record.budget_id.company_id != record.company_id:
                raise ValidationError(
                    "El presupuesto relacionado pertenece a otra empresa."
                )

    def action_plan(self): self.write({"state": "planned"})
    def action_start(self): self.write({"state": "in_progress"})
    def action_done(self): self.write({"state": "done"})
    def action_cancel(self): self.write({"state": "cancelled"})
    def action_set_draft(self): self.write({"state": "draft"})


class StepManagementPlanLine(models.Model):
    _name = "step.management.plan.line"
    _description = "Tarea del plan operacional"
    _order = "date, sequence, id"
    _check_company_auto = True

    plan_id = fields.Many2one("step.management.plan", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="plan_id.company_id", store=True, index=True)
    sequence = fields.Integer(default=10)
    date = fields.Date(string="Fecha", required=True)
    center_id = fields.Many2one(
        "step.management.cost.center", string="Centro de costo", check_company=True,
    )
    indicator = fields.Char(string="Tarea / indicador", required=True)
    responsible_id = fields.Many2one("res.users", string="Responsable")
    quantity = fields.Float(string="Cantidad", digits=(16, 4))
    uom_id = fields.Many2one("uom.uom", string="UdM")
    week_label = fields.Char(string="Semana", index=True)
    iso_year = fields.Integer(string="Año ISO")
    iso_week = fields.Integer(string="Semana ISO")
    generated = fields.Boolean(
        string="Generada", default=False, index=True,
        help="Tarea creada por «Generar tareas semanales»; se recrea al "
             "regenerar. Las tareas manuales no se tocan.",
    )
    budget_line_id = fields.Many2one(
        "step.management.budget.line", string="Línea de presupuesto",
        ondelete="set null", check_company=True, index=True,
    )
    state = fields.Selection(
        [("pending", "Pendiente"), ("in_progress", "En curso"), ("done", "Terminada"), ("cancelled", "Cancelada")],
        default="pending", required=True,
    )
    notes = fields.Char(string="Observación")
