from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class StepManagementPlan(models.Model):
    _name = "step.management.plan"
    _description = "Plan operacional"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_start desc, id desc"

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
    budget_id = fields.Many2one("step.management.operational.budget", string="Presupuesto relacionado")
    center_ids = fields.Many2many("step.management.cost.center", string="Centros de costo")
    date_start = fields.Date(string="Inicio", required=True, tracking=True)
    date_end = fields.Date(string="Término", required=True, tracking=True)
    week_reference = fields.Char(string="Semana / referencia")
    line_ids = fields.One2many("step.management.plan.line", "plan_id", string="Tareas")
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

    def action_plan(self): self.write({"state": "planned"})
    def action_start(self): self.write({"state": "in_progress"})
    def action_done(self): self.write({"state": "done"})
    def action_cancel(self): self.write({"state": "cancelled"})
    def action_set_draft(self): self.write({"state": "draft"})


class StepManagementPlanLine(models.Model):
    _name = "step.management.plan.line"
    _description = "Tarea del plan operacional"
    _order = "date, sequence, id"

    plan_id = fields.Many2one("step.management.plan", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    date = fields.Date(string="Fecha", required=True)
    center_id = fields.Many2one("step.management.cost.center", string="Centro de costo")
    indicator = fields.Char(string="Tarea / indicador", required=True)
    responsible_id = fields.Many2one("res.users", string="Responsable")
    quantity = fields.Float(string="Cantidad", digits=(16, 4))
    uom_id = fields.Many2one("uom.uom", string="UdM")
    state = fields.Selection(
        [("pending", "Pendiente"), ("in_progress", "En curso"), ("done", "Terminada"), ("cancelled", "Cancelada")],
        default="pending", required=True,
    )
    notes = fields.Char(string="Observación")
