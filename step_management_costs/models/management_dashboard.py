from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class StepManagementDashboard(models.Model):
    _inherit = "step.management.operational.budget"

    @api.model
    def get_management_dashboard(self, days=0):
        days = max(int(days or 0), 0)
        domain = []
        if days:
            start = fields.Date.context_today(self) - relativedelta(days=days)
            domain = [("date", ">=", start)]
        budgets = self.search(domain)
        approved = budgets.filtered(lambda record: record.state in ("approved", "closed"))
        plans = self.env["step.management.plan"].search(
            [("date_start", ">=", start)] if days else []
        )
        costs = self.env["step.management.historical.cost"].search(domain)
        centers = self.env["step.management.cost.center"].search([("active", "=", True)])
        templates = self.env["step.management.budget.template"].search([("state", "=", "active")])
        return {
            "period_days": days,
            "budgets": {
                "total": len(budgets),
                "draft": len(budgets.filtered(lambda record: record.state == "draft")),
                "approved": len(approved),
                "amount": sum(budgets.mapped("total_amount")),
                "hectares": sum(budgets.mapped("total_hectares")),
            },
            "centers": {"total": len(centers), "hectares": sum(centers.mapped("hectares"))},
            "templates": len(templates),
            "plans": {
                "total": len(plans),
                "open": len(plans.filtered(lambda record: record.state not in ("done", "cancelled"))),
            },
            "costs": {
                "actual": sum(costs.mapped("actual_amount")),
                "budget": sum(costs.mapped("budget_amount")),
                "variance": sum(costs.mapped("variance")),
            },
            "recent": [{
                "id": budget.id,
                "name": budget.name,
                "description": budget.description,
                "season": budget.season,
                "state": budget.state,
                "hectares": budget.total_hectares,
                "amount": budget.total_amount,
            } for budget in budgets.sorted("date", reverse=True)[:6]],
        }
