"""Asistente de comparación Presupuesto vs. Real (desviación auditable).

No persiste nada: recalcula cada vez desde `budget.month` (presupuesto) y desde
la contabilidad analítica publicada (real). Cada línea permite el drill-down a
los `account.move.line` que la componen.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import float_round

from ..models.budget_import import MONTH_SELECTION


class StepManagementBudgetVarianceWizard(models.TransientModel):
    _name = "step.management.budget.variance.wizard"
    _description = "Presupuesto vs. real"

    budget_id = fields.Many2one(
        "step.management.operational.budget", string="Presupuesto", required=True, ondelete="cascade",
    )
    company_id = fields.Many2one(related="budget_id.company_id")
    currency_id = fields.Many2one(related="budget_id.currency_id")
    date_from = fields.Date(string="Desde", required=True)
    date_to = fields.Date(string="Hasta", required=True)
    only_deviations = fields.Boolean(string="Sólo con desviación")
    computed = fields.Boolean(default=False)
    line_ids = fields.One2many("step.management.budget.variance.line", "wizard_id", string="Detalle")

    total_budget_cost = fields.Monetary(compute="_compute_totals", currency_field="currency_id")
    total_actual_cost = fields.Monetary(compute="_compute_totals", currency_field="currency_id")
    total_variance_cost = fields.Monetary(compute="_compute_totals", currency_field="currency_id")
    variance_pct_cost = fields.Float(compute="_compute_totals", string="Var % costo")
    total_budget_income = fields.Monetary(compute="_compute_totals", currency_field="currency_id")
    total_actual_income = fields.Monetary(compute="_compute_totals", currency_field="currency_id")

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise ValidationError(_("La fecha «Desde» no puede ser posterior a «Hasta»."))

    @api.depends("line_ids.budget_amount", "line_ids.actual_amount", "line_ids.flow_type")
    def _compute_totals(self):
        for wiz in self:
            cost = wiz.line_ids.filtered(lambda l: l.flow_type == "cost")
            income = wiz.line_ids.filtered(lambda l: l.flow_type == "income")
            wiz.total_budget_cost = sum(cost.mapped("budget_amount"))
            wiz.total_actual_cost = sum(cost.mapped("actual_amount"))
            wiz.total_variance_cost = wiz.total_actual_cost - wiz.total_budget_cost
            wiz.variance_pct_cost = (
                wiz.total_variance_cost * 100.0 / wiz.total_budget_cost
                if wiz.total_budget_cost else 0.0
            )
            wiz.total_budget_income = sum(income.mapped("budget_amount"))
            wiz.total_actual_income = sum(income.mapped("actual_amount"))

    def action_compute(self):
        self.ensure_one()
        self.line_ids.unlink()
        budget = self.budget_id

        # lado presupuesto: agregado por (centro, grupo, mes, naturaleza)
        rounding = self.currency_id.rounding or 0.01
        agg = {}
        for line in budget.line_ids:
            for month in line.month_ids:
                key = (line.center_id.id, line.group_id.id, month.month, line.flow_type or "cost")
                b = agg.setdefault(key, {"budget_amount": 0.0, "budget_qty": 0.0,
                                         "actual_amount": 0.0, "actual_qty": 0.0,
                                         "move_line_ids": self.env["account.move.line"]})
                b["budget_amount"] += month.amount
                b["budget_qty"] += month.quantity

        # lado real: contabilidad analítica publicada
        for bucket in budget._read_analytic_actuals(self.date_from, self.date_to):
            key = (bucket["center_id"], bucket["group_id"], bucket["month"], bucket["flow_type"])
            b = agg.setdefault(key, {"budget_amount": 0.0, "budget_qty": 0.0,
                                     "actual_amount": 0.0, "actual_qty": 0.0,
                                     "move_line_ids": self.env["account.move.line"]})
            b["actual_amount"] += bucket["actual_amount"]
            b["actual_qty"] += bucket["actual_qty"]
            b["move_line_ids"] |= bucket["move_line_ids"]

        cmds = []
        for (center_id, group_id, month, flow_type), b in agg.items():
            variance = b["actual_amount"] - b["budget_amount"]
            if self.only_deviations and float_round(variance, precision_rounding=rounding) == 0.0:
                continue
            cmds.append((0, 0, {
                "center_id": center_id or False,
                "group_id": group_id or False,
                "month": month or False,
                "flow_type": flow_type,
                "budget_amount": b["budget_amount"],
                "budget_qty": b["budget_qty"],
                "actual_amount": b["actual_amount"],
                "actual_qty": b["actual_qty"],
                "variance": variance,
                "variance_percent": (variance * 100.0 / b["budget_amount"]) if b["budget_amount"] else 0.0,
                "move_line_ids": [(6, 0, b["move_line_ids"].ids)],
            }))
        self.write({"line_ids": cmds, "computed": True})
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name, "res_id": self.id,
            "view_mode": "form", "target": "new",
        }


class StepManagementBudgetVarianceLine(models.TransientModel):
    _name = "step.management.budget.variance.line"
    _description = "Línea de desviación presupuesto/real"
    _order = "center_id, group_id, month"

    wizard_id = fields.Many2one("step.management.budget.variance.wizard", required=True, ondelete="cascade")
    currency_id = fields.Many2one(related="wizard_id.currency_id")
    center_id = fields.Many2one("step.management.cost.center", string="Centro")
    group_id = fields.Many2one("step.management.budget.group", string="Grupo")
    group_label = fields.Char(compute="_compute_group_label", string="Grupo")
    month = fields.Selection(MONTH_SELECTION, string="Mes")
    flow_type = fields.Selection([("cost", "Costo"), ("income", "Ingreso")], string="Naturaleza")
    budget_amount = fields.Monetary(string="Presupuesto", currency_field="currency_id")
    budget_qty = fields.Float(string="Cant. ppto", digits=(16, 4))
    actual_amount = fields.Monetary(string="Real", currency_field="currency_id")
    actual_qty = fields.Float(string="Cant. real", digits=(16, 4))
    variance = fields.Monetary(string="Var $", currency_field="currency_id")
    variance_percent = fields.Float(string="Var %")
    move_line_ids = fields.Many2many("account.move.line", string="Apuntes")
    move_count = fields.Integer(compute="_compute_move_count")

    @api.depends("group_id")
    def _compute_group_label(self):
        for line in self:
            line.group_label = line.group_id.display_name or _("Sin clasificar")

    @api.depends("move_line_ids")
    def _compute_move_count(self):
        for line in self:
            line.move_count = len(line.move_line_ids)

    def action_open_moves(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Apuntes contables"),
            "res_model": "account.move.line",
            "view_mode": "list,form",
            "domain": [("id", "in", self.move_line_ids.ids)],
            "target": "current",
        }
