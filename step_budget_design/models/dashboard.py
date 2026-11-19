"""Read the existing budget, agricultural and estimation masters for the panel."""
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.addons.step_management_costs.models.management_dashboard import _hectares_breakdown


def token(value):
    return (value or "").strip().casefold()


def season_matches(record, season=None, label=None):
    if season and record.season_id:
        return record.season_id == season
    labels = {token(label)} if label else {token(season.name), token(season.code)}
    return bool(token(record.season) and token(record.season) in labels)


def species_key(center):
    return ("master", center.especie_id.id) if center.especie_id else ("legacy", token(center.species))


def table_totals(rows, sums, averages=()):
    """A missing amount stays missing; averages follow Excel's blank handling."""
    result = {}
    for name in sums:
        values = [row[name] for row in rows]
        result[name] = sum(values) if all(value is not None for value in values) else None
    for name in averages:
        values = [row[name] for row in rows if row[name] is not None]
        result[name] = sum(values) / len(values) if values else None
    return result


class BudgetDashboard(models.Model):
    _inherit = "step.management.operational.budget"

    @api.model
    def _panel_filter_record(self, records, selected):
        if not selected:
            return records.browse()
        record = records.filtered(lambda row: row.id == int(selected))
        if not record:
            raise ValidationError(_("Seleccione un filtro disponible para la empresa activa."))
        return record

    def _panel_estimated_kilos(self, centers, estimates):
        """Use one current validated document per center, not its revisions twice."""
        self.ensure_one()
        missing = set(centers.ids)
        kilos = 0.0
        for estimate in estimates:
            if not season_matches(estimate, self.season_id, self.season):
                continue
            lines = estimate.line_ids.filtered(lambda line: line.center_id.id in missing)
            kilos += sum(lines.mapped("total_kg"))
            missing.difference_update(lines.center_id.ids)
            if not missing:
                break
        return {
            "estimated_kg": kilos if centers and not missing else None,
            "estimated_centers": len(centers) - len(missing),
            "center_count": len(centers),
        }

    @api.model
    def _panel_center_budgets(self, budgets, estimates, matches, conversion):
        """One native center per row, without repeating its hectares or estimates."""
        rows, estimate_keys = {}, {}
        for budget in budgets:
            lines = budget.line_ids.filtered(lambda line: matches(line.center_id))
            centers = (budget.allocation_ids.center_id | lines.center_id).filtered(matches)
            factor = conversion(budget)
            for center in centers:
                row = rows.setdefault(center.id, {
                    "id": center.id, "name": center.display_name, "hectares": center.hectares,
                    "harvest": 0.0, "maintenance": 0.0, "amount": 0.0,
                    "estimated_kg": 0.0, "conversion_available": True,
                    "estimation_available": True,
                })
                costs = lines.filtered(lambda line: line.center_id == center and line.flow_type != "income")
                amount = sum(costs.mapped("amount"))
                harvest = sum(costs.filtered(lambda line: token(line.activity_id.name) == "cosechar").mapped("amount"))
                row["conversion_available"] &= factor["available"] or not amount
                row["harvest"] += harvest * factor["factor"]
                row["maintenance"] += (amount - harvest) * factor["factor"]
                row["amount"] += amount * factor["factor"]
                estimate = estimates.filtered(lambda candidate: season_matches(candidate, budget.season_id, budget.season)
                    and center in candidate.line_ids.center_id)[:1]
                if not estimate:
                    row["estimation_available"] = False
                    continue
                key = (center.id, estimate.id)
                if key not in estimate_keys:
                    row["estimated_kg"] += sum(estimate.line_ids.filtered(lambda line: line.center_id == center).mapped("total_kg"))
                    estimate_keys[key] = True
        for row in rows.values():
            if not row["estimation_available"]:
                row["estimated_kg"] = None
            if not row["conversion_available"]:
                row.update(harvest=None, maintenance=None, amount=None)
            row["cost_per_kg"] = (row["amount"] / row["estimated_kg"]
                if row["conversion_available"] and row["estimated_kg"] else None)
            row["cost_per_ha"] = (row["amount"] / row["hectares"]
                if row["conversion_available"] and row["hectares"] else None)
        return list(rows.values())

    @api.model
    def get_management_dashboard(self, days=0, season_id=False, species_id=False, currency_id=False):
        days = max(int(days or 0), 0)
        company = self.env.company
        company_domain = [("company_id", "in", [False, company.id])]
        seasons = self.env["step.temporada"].search(company_domain, order="start_date desc, id desc")
        species_catalog = self.env["step.especie"].search(company_domain, order="name, id")
        currencies = self.env["res.currency"].with_context(active_test=False).search([
            ("name", "in", ["CLP", "USD"]),
        ], order="name")
        season = self._panel_filter_record(seasons, season_id)
        species = self._panel_filter_record(species_catalog, species_id)
        currency = self._panel_filter_record(currencies, currency_id)
        currency = currency or currencies.filtered(lambda row: row == company.currency_id) or currencies[:1]
        if not currency:
            raise ValidationError(_("Configure las monedas CLP o USD en el maestro de monedas."))

        def center_matches(center):
            return not species or (
                center.especie_id == species if center.especie_id else token(center.species) == token(species.name)
            )

        domain = [("company_id", "=", company.id), ("state", "not in", ["cancelled", "superseded"])]
        if days:
            start = fields.Date.context_today(self) - relativedelta(days=days)
            domain.append(("date", ">=", start))
        budgets = self.search(domain)
        if season:
            budgets = budgets.filtered(lambda budget: season_matches(budget, season))
        estimates = self.env["step.management.estimation"].search([
            ("company_id", "=", company.id), ("state", "=", "validated"),
        ], order="validated_at desc, date desc, id desc")
        exchange = self.env["step.management.exchange.rate"]
        conversion_cache = {}

        def factor(budget):
            key = (budget.currency_id.id, budget.date, budget.conversion_rate_type)
            if key not in conversion_cache:
                conversion_cache[key] = exchange.get_conversion(
                    1.0, budget.currency_id, currency, company, budget.date, budget.conversion_rate_type,
                )
            return conversion_cache[key]

        totals = {"amount": 0.0, "investment": 0.0, "hectares": 0.0, "missing_rates": 0}
        projected = {}
        recent = []
        selected_budgets = self.browse()
        selected_centers = self.env["account.analytic.account"]
        for budget in budgets:
            lines = budget.line_ids.filtered(lambda line: center_matches(line.center_id))
            allocations = budget.allocation_ids.filtered(lambda row: center_matches(row.center_id))
            if species and not lines and not allocations:
                continue
            selected_budgets |= budget
            centers = allocations.center_id | lines.center_id
            selected_centers |= centers
            costs = lines.filtered(lambda line: line.flow_type != "income")
            investment = costs.filtered(lambda line: line.center_id.etapa_costo in ("inver", "cre"))
            operational = costs - investment
            conversion = factor(budget)
            available = conversion["available"]
            multiplier = conversion["factor"]
            totals["missing_rates"] += int(not available and any(lines.mapped("amount")))
            totals["amount"] += sum(operational.mapped("amount")) * multiplier
            totals["investment"] += sum(investment.mapped("amount")) * multiplier
            hectares = sum(allocations.mapped("hectares")) if allocations else sum(centers.mapped("hectares"))
            totals["hectares"] += hectares

            for line in lines.filtered(lambda row: row.center_id.etapa_costo not in ("inver", "cre")):
                key = species_key(line.center_id)
                row = projected.setdefault(key, {
                    "key": "%s:%s" % key,
                    "species": line.center_id.especie_id.name or line.center_id.species or _("Sin especie"),
                    "income": 0.0, "cost": 0.0, "available": True,
                })
                row["available"] &= available or not line.amount
                row["income" if line.flow_type == "income" else "cost"] += line.amount * multiplier

            harvest = costs.filtered(lambda line: token(line.activity_id.name) == "cosechar")
            harvest_amount = sum(harvest.mapped("amount"))
            amount = sum(costs.mapped("amount"))
            kilo_data = budget._panel_estimated_kilos(centers, estimates)
            kg = kilo_data["estimated_kg"]
            recent.append({
                "id": budget.id, "name": budget.name, "description": budget.description,
                "season": budget.season_id.name or budget.season, "state": budget.state,
                "hectares": hectares, "currency": currency.name,
                "conversion_available": available,
                "harvest": harvest_amount * multiplier if available else None,
                "maintenance": (amount - harvest_amount) * multiplier if available else None,
                "amount": amount * multiplier if available else None,
                "cost_per_kg": amount * multiplier / kg if available and kg else None,
                "cost_per_ha": amount * multiplier / hectares if available and hectares else None,
                **kilo_data,
            })

        recent_centers = self._panel_center_budgets(selected_budgets, estimates, center_matches, factor)
        for row in projected.values():
            row["result"] = row["income"] - row["cost"]
            if not row["available"]:
                row.update(income=None, cost=None, result=None)
        if totals["missing_rates"]:
            totals.update(amount=None, investment=None)

        centers = self.env["account.analytic.account"].search([
            ("active", "=", True), *company_domain,
            "|", "|", ("type_costo", "!=", False), ("cost_type", "!=", False),
            ("id", "in", selected_centers.ids),
        ]).filtered(center_matches)
        templates = self.env["step.management.budget.template"].search([
            ("company_id", "=", company.id), ("state", "=", "active"),
        ]).filtered(lambda row: (not season or row.season_id == season) and (not species or row.species_id == species))
        plan_domain = [("company_id", "=", company.id)]
        if days:
            plan_domain.append(("date_start", ">=", start))
        plans = self.env["step.management.plan"].search(plan_domain).filtered(
            lambda row: (not season or row.budget_id in selected_budgets
                         or token(row.season) in {token(season.name), token(season.code)})
            and (not species or row.budget_id in selected_budgets
                 or any(center_matches(center) for center in row.center_ids))
        )
        cost_domain = [("company_id", "=", company.id)]
        if days:
            cost_domain.append(("date", ">=", start))
        costs = self.env["step.management.historical.cost"].search(cost_domain).filtered(
            lambda row: (not season or token(row.season) in {token(season.name), token(season.code)})
            and (not species or center_matches(row.center_id))
            and row.center_id.etapa_costo not in ("inver", "cre")
        )
        real_results, budget_results = [], []
        for cost in costs:
            for amount, results in ((cost.actual_amount, real_results), (cost.budget_amount, budget_results)):
                results.append(exchange.get_conversion(
                    amount, cost.currency_id, currency, company, cost.date, "actual",
                ))
        stock_domain = [("company_id", "=", company.id), ("requirement_id.active", "=", True)]
        if days:
            stock_domain.append(("requirement_id.date", ">=", start))
        if season:
            stock_domain.append(("requirement_id.season", "in", [season.name, season.code]))
        if species:
            stock_domain.append(("requirement_id.budget_ids", "in", selected_budgets.ids))
        stock_lines = self.env["step.management.stock.requirement.line"].search(stock_domain)
        return {
            "period_days": days,
            "filters": {
                "season_id": season.id, "species_id": species.id, "currency_id": currency.id,
                "seasons": [{"id": row.id, "name": row.name} for row in seasons],
                "species": [{"id": row.id, "name": row.name} for row in species_catalog],
                "currencies": [{"id": row.id, "name": row.name} for row in currencies],
            },
            "currencies": {"company": company.currency_id.name, "reporting": currency.name, "selected": currency.name},
            "budgets": {
                "total": len(selected_budgets),
                "draft": len(selected_budgets.filtered(lambda row: row.state == "draft")),
                "approved": len(selected_budgets.filtered(lambda row: row.state in ("approved", "closed"))),
                "amount_reporting": totals["amount"],
                "reporting_available": len(selected_budgets) - totals["missing_rates"], **totals,
            },
            "projected": sorted(projected.values(), key=lambda row: row["species"]),
            "projected_total": table_totals(list(projected.values()), ("income", "cost", "result")),
            "recent": recent[:6],
            "recent_centers": recent_centers,
            "recent_total": table_totals(recent_centers,
                ("hectares", "harvest", "maintenance", "amount", "estimated_kg"),
                ("cost_per_kg", "cost_per_ha")),
            "centers": {"total": len(centers), "hectares": sum(centers.mapped("hectares"))},
            "templates": len(templates),
            "plans": {"total": len(plans), "open": len(plans.filtered(lambda row: row.state not in ("done", "cancelled")))},
            "costs": self._dashboard_costs_block(real_results, budget_results),
            "hectares_by_farm_species": _hectares_breakdown(centers, ("farm", "species")),
            "hectares_by_variety": _hectares_breakdown(centers, ("variety",)),
            "stock": {
                "line_count": len(stock_lines), "needs": sum(stock_lines.mapped("total_quantity")),
                "available": sum(stock_lines.mapped("available_quantity")),
                "committed": sum(stock_lines.mapped("committed_quantity")),
                "net_to_buy": sum(stock_lines.mapped("net_to_buy")),
            },
        }
