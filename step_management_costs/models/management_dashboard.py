from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

from .exchange_rate import default_conversion_currency


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
        company = self.env.company
        company_currency = company.currency_id
        reporting_currency = default_conversion_currency(self.env)
        exchange_service = self.env["step.management.exchange.rate"]

        def converted(amount, source_currency, target_currency, conversion_date, rate_type):
            return exchange_service.get_conversion(
                amount, source_currency, target_currency, company, conversion_date, rate_type,
            )

        budget_company_results = [
            converted(
                budget.total_amount, budget.currency_id, company_currency,
                budget.date, budget.conversion_rate_type,
            ) for budget in budgets
        ]
        budget_reporting_results = [
            converted(
                budget.total_amount, budget.currency_id, reporting_currency,
                budget.date, "estimated",
            ) for budget in budgets
        ]
        cost_budget_results = [
            converted(cost.budget_amount, cost.currency_id, company_currency, cost.date, "actual")
            for cost in costs
        ]
        cost_actual_results = [
            converted(cost.actual_amount, cost.currency_id, company_currency, cost.date, "actual")
            for cost in costs
        ]
        return {
            "period_days": days,
            "budgets": {
                "total": len(budgets),
                "draft": len(budgets.filtered(lambda record: record.state == "draft")),
                "approved": len(approved),
                "amount": sum(result["amount"] for result in budget_company_results if result["available"]),
                "amount_reporting": sum(
                    result["amount"] for result in budget_reporting_results if result["available"]
                ),
                "reporting_available": sum(
                    1 for result in budget_reporting_results if result["available"]
                ),
                "hectares": sum(budgets.mapped("total_hectares")),
            },
            "centers": {"total": len(centers), "hectares": sum(centers.mapped("hectares"))},
            "templates": len(templates),
            "plans": {
                "total": len(plans),
                "open": len(plans.filtered(lambda record: record.state not in ("done", "cancelled"))),
            },
            "costs": {
                "actual": sum(result["amount"] for result in cost_actual_results if result["available"]),
                "budget": sum(result["amount"] for result in cost_budget_results if result["available"]),
                "variance": sum(result["amount"] for result in cost_actual_results if result["available"])
                    - sum(result["amount"] for result in cost_budget_results if result["available"]),
            },
            "currencies": {
                "company": company_currency.name,
                "reporting": reporting_currency.name,
            },
            "recent": [{
                "id": budget.id,
                "name": budget.name,
                "description": budget.description,
                "season": budget.season,
                "state": budget.state,
                "hectares": budget.total_hectares,
                "amount": budget.total_amount,
                "currency": budget.currency_id.name,
                "amount_converted": budget.total_amount_converted,
                "conversion_currency": budget.conversion_currency_id.name,
                "conversion_available": budget.conversion_available,
            } for budget in budgets.sorted("date", reverse=True)[:6]],
        }
