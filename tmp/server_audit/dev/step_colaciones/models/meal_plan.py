from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class StepColacionPlan(models.Model):
    _name = "step.colacion.plan"
    _description = "Plan semanal de colaciones"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "week_start desc, id desc"

    name = fields.Char(required=True, default=lambda self: _("Nueva planificación"), tracking=True)
    week_start = fields.Date(string="Inicio de semana", required=True, default=fields.Date.context_today, tracking=True)
    week_end = fields.Date(string="Fin de semana", compute="_compute_week_end", store=True)
    department_id = fields.Many2one("hr.department", string="Departamento", required=True, tracking=True)
    supplier_id = fields.Many2one(
        "res.partner", string="Proveedor", required=True, tracking=True,
        domain="[('is_meal_supplier', '=', True)]",
    )
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True, readonly=True)
    line_ids = fields.One2many("step.colacion.plan.line", "plan_id", string="Detalle", copy=True)
    total_quantity = fields.Integer(string="Total colaciones", compute="_compute_totals", store=True)
    total_cost = fields.Monetary(string="Costo planificado", compute="_compute_totals", store=True, currency_field="currency_id")
    state = fields.Selection(
        [("draft", "Borrador"), ("approved", "Aprobado"), ("done", "Finalizado"), ("cancelled", "Anulado")],
        default="draft", required=True, tracking=True, index=True,
    )
    notes = fields.Html(string="Notas")
    legacy_ref = fields.Char(copy=False, index=True)

    _sql_constraints = [
        (
            "plan_scope_unique",
            "unique(week_start, department_id, supplier_id, company_id)",
            "Ya existe una planificación para esta semana, departamento y proveedor.",
        ),
        ("legacy_ref_unique", "unique(legacy_ref)", "La planificación de origen ya fue migrada."),
    ]

    @api.depends("week_start")
    def _compute_week_end(self):
        for plan in self:
            plan.week_end = plan.week_start + timedelta(days=6) if plan.week_start else False

    @api.depends("line_ids.total_quantity", "line_ids.total_cost")
    def _compute_totals(self):
        for plan in self:
            plan.total_quantity = sum(plan.line_ids.mapped("total_quantity"))
            plan.total_cost = sum(plan.line_ids.mapped("total_cost"))

    @api.constrains("week_start")
    def _check_monday(self):
        for plan in self.filtered("week_start"):
            if plan.week_start.weekday() != 0:
                raise ValidationError(_("El inicio de la planificación debe corresponder a un lunes."))

    @api.onchange("week_start")
    def _onchange_week_start(self):
        if self.week_start and self.week_start.weekday() != 0:
            self.week_start = self.week_start - timedelta(days=self.week_start.weekday())

    def action_approve(self):
        Tariff = self.env["step.colacion.tariff"]
        for plan in self:
            if not plan.line_ids:
                raise UserError(_("Agregue al menos un producto al plan."))
            for line in plan.line_ids:
                rate = Tariff.find_rate(line.product_tmpl_id, plan.supplier_id, plan.company_id, plan.week_start)
                if not rate:
                    raise UserError(_(
                        "No existe tarifa vigente para %(product)s al inicio de la semana.",
                        product=line.product_tmpl_id.display_name,
                    ))
                line.unit_cost = rate.price
            plan.state = "approved"

    def action_done(self):
        self.write({"state": "done"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def action_draft(self):
        self.write({"state": "draft"})


class StepColacionPlanLine(models.Model):
    _name = "step.colacion.plan.line"
    _description = "Detalle del plan semanal de colaciones"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    plan_id = fields.Many2one("step.colacion.plan", required=True, ondelete="cascade", index=True)
    product_tmpl_id = fields.Many2one(
        "product.template", string="Producto", required=True,
        domain="[('is_meal', '=', True)]",
    )
    monday = fields.Integer(string="Lunes", default=0)
    tuesday = fields.Integer(string="Martes", default=0)
    wednesday = fields.Integer(string="Miércoles", default=0)
    thursday = fields.Integer(string="Jueves", default=0)
    friday = fields.Integer(string="Viernes", default=0)
    saturday = fields.Integer(string="Sábado", default=0)
    sunday = fields.Integer(string="Domingo", default=0)
    total_quantity = fields.Integer(string="Total", compute="_compute_totals", store=True)
    unit_cost = fields.Monetary(string="Tarifa", currency_field="currency_id", default=0)
    total_cost = fields.Monetary(string="Costo", compute="_compute_totals", store=True, currency_field="currency_id")
    currency_id = fields.Many2one(related="plan_id.currency_id", store=True, readonly=True)
    company_id = fields.Many2one(related="plan_id.company_id", store=True, readonly=True)

    _sql_constraints = [
        ("plan_product_unique", "unique(plan_id, product_tmpl_id)", "El producto solo puede aparecer una vez en el plan."),
        (
            "daily_quantities_nonnegative",
            "check(monday >= 0 and tuesday >= 0 and wednesday >= 0 and thursday >= 0 and friday >= 0 and saturday >= 0 and sunday >= 0)",
            "Las cantidades diarias no pueden ser negativas.",
        ),
    ]

    @api.depends(
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "unit_cost"
    )
    def _compute_totals(self):
        for line in self:
            line.total_quantity = sum([
                line.monday, line.tuesday, line.wednesday, line.thursday,
                line.friday, line.saturday, line.sunday,
            ])
            line.total_cost = line.total_quantity * line.unit_cost

    def write(self, vals):
        if any(line.plan_id.state != "draft" for line in self) and set(vals) - {"unit_cost"}:
            raise UserError(_("No puede modificar una planificación que ya fue aprobada."))
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            plan = self.env["step.colacion.plan"].browse(values.get("plan_id"))
            if plan and plan.state != "draft":
                raise UserError(_("No puede agregar productos a una planificación aprobada."))
        return super().create(vals_list)
