from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _

from .exchange_rate import default_conversion_currency

#: Corte V2 F — bloques 2 y 3 del tablero: hectáreas por fundo/especie y por
#: variedad. Se agrupa en Python (no `read_group`) porque la clave es una
#: combinación de campos `Char` normalizados con `strip()`; los centros sin
#: dato quedan agrupados bajo «Sin clasificar», nunca se ocultan ni se
#: reparten en un grupo existente por adivinanza.
UNCLASSIFIED = _("Sin clasificar")


def _hectares_breakdown(centers, key_fields):
    """`key_fields`: tupla de nombres de campo Char sobre `centers`. Devuelve
    una lista de filas `{<campo>: valor, "hectares": total}` ordenada
    descendente por hectáreas, sin mezclar centros sin dato con los que sí
    lo tienen."""
    buckets = {}
    for center in centers:
        key = tuple((getattr(center, field) or "").strip() or None for field in key_fields)
        buckets.setdefault(key, 0.0)
        buckets[key] += center.hectares
    rows = []
    for key, hectares in buckets.items():
        row = {field: (value or UNCLASSIFIED) for field, value in zip(key_fields, key)}
        row["hectares"] = hectares
        rows.append(row)
    rows.sort(key=lambda row: row["hectares"], reverse=True)
    return rows


class StepManagementDashboard(models.Model):
    _inherit = "step.management.operational.budget"

    @staticmethod
    def _dashboard_costs_block(cost_actual_results, cost_budget_results):
        """Bloque «real vs. presupuesto» (tablero, bloque 1). La variación %
        se calcula desde los totales ya sumados — nunca promediando ni
        sumando porcentajes de filas individuales — y queda en 0.0 (con
        `budget_available=False`) cuando no hay base de comparación, en vez
        de una división por cero disfrazada de 0%."""
        actual = sum(result["amount"] for result in cost_actual_results if result["available"])
        budget = sum(result["amount"] for result in cost_budget_results if result["available"])
        variance = actual - budget
        return {
            "actual": actual, "budget": budget, "variance": variance,
            "variance_percent": (variance * 100.0 / budget) if budget else 0.0,
            "budget_available": bool(budget),
        }

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
        stock_line_domain = [("company_id", "=", company.id), ("requirement_id.active", "=", True)]
        if days:
            stock_line_domain.append(("requirement_id.date", ">=", start))
        stock_lines = self.env["step.management.stock.requirement.line"].search(stock_line_domain)
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
            "costs": self._dashboard_costs_block(cost_actual_results, cost_budget_results),
            # Corte V2 F, bloques 2 y 3 del tablero: hectáreas por
            # fundo/especie y por variedad — siempre sobre los centros
            # activos (no filtra por `days`: son datos de maestro vigente,
            # no eventos con fecha).
            "hectares_by_farm_species": _hectares_breakdown(centers, ("farm", "species")),
            "hectares_by_variety": _hectares_breakdown(centers, ("variety",)),
            # Corte V2 F, punto 4: necesidades/disponible/comprometido/neto
            # cuando existan documentos de necesidades de stock (V2 C). Sin
            # documentos, se muestran ceros reales (no se ocultan campos ni
            # se disfraza la ausencia de datos).
            "stock": {
                "line_count": len(stock_lines),
                "needs": sum(stock_lines.mapped("total_quantity")),
                "available": sum(stock_lines.mapped("available_quantity")),
                "committed": sum(stock_lines.mapped("committed_quantity")),
                "net_to_buy": sum(stock_lines.mapped("net_to_buy")),
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
