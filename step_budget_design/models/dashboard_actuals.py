"""Read the same booked ledger as Costos reales, retaining its access rules."""
from math import isfinite

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError

from .dashboard import relative_variance, table_totals, token


class BudgetDashboardActuals(models.Model):
    _inherit = "step.management.operational.budget"

    @api.model
    def _panel_control_data(self, accounting, budgets):
        actuals = {row["id"]: row for row in accounting["rows"] if row["stage"] == "ope"}
        planned = {row["id"]: row for row in budgets if row["stage"] == "ope"}
        rows = []
        for ident in dict.fromkeys([*planned, *actuals]):
            budget, actual = planned.get(ident), actuals.get(ident)
            master = budget or actual
            available = accounting["access"] and (not actual or actual["available"])
            row = {"id": ident, "name": master["name"], "hectares": master["hectares"],
                "maintenance": actual["maintenance"] if actual else 0.0 if available else None,
                "harvest": actual["harvest"] if actual else 0.0 if available else None,
                "amount": actual["amount"] if actual else 0.0 if available else None,
                "budget": budget["amount"] if budget else 0.0}
            row["difference"] = row["amount"] - row["budget"] if row["amount"] is not None and row["budget"] is not None else None
            row["variation"] = relative_variance(row["amount"], row["budget"])
            row["cost_per_ha"] = row["amount"] / row["hectares"] if row["amount"] is not None and row["hectares"] else None
            rows.append(row)
        total = table_totals(rows, ("hectares", "maintenance", "harvest", "amount", "budget", "difference"))
        if not accounting["access"]:
            total.update(maintenance=None, harvest=None, amount=None, difference=None)
        total["variation"] = relative_variance(total["amount"], total["budget"])
        total["cost_per_ha"] = total["amount"] / total["hectares"] if total["amount"] is not None and total["hectares"] else None
        sums = {stage: table_totals([row for row in accounting["rows"] if row["stage"] in stages], ("amount",))["amount"]
                if accounting["access"] else None for stage, stages in (("operating", ("ope",)), ("investment", ("inver", "cre")))}
        return {"access": accounting["access"], "rows": rows, "total": total,
            "operating_actual": sums["operating"], "investment_actual": sums["investment"],
            "unavailable_centers": sum(not row["available"] for row in accounting["rows"])}

    @api.model
    def _panel_harvest_share(self, row, analytics):
        """Correlated activities use the center's weight; independent plans use 100%."""
        activity_plan = self.env.company.management_actual_activity_plan_id
        center_plan = self.env.company.management_actual_center_plan_id
        local, independent = [], []
        for key, weight in (row.analytic_distribution or {}).items():
            ids = {int(value.strip()) for value in str(key).split(",") if value.strip().isdigit()}
            activities = [analytics[ident] for ident in ids if ident in analytics
                          and analytics[ident].root_plan_id == activity_plan]
            if not activities:
                continue
            if len(activities) != 1 or not isfinite(float(weight)) or float(weight) < 0:
                return None
            centers = {ident for ident in ids if ident in analytics
                       and analytics[ident].root_plan_id == center_plan}
            entry = (float(weight), token(activities[0].name) == "cosechar")
            if row.center_id.id in centers:
                local.append(entry)
            elif not centers:
                independent.append(entry)
        entries, denominator = (local, row.percentage) if local else (independent, 100.0)
        if not entries:
            return 0.0
        if denominator <= 0 or sum(weight for weight, harvest in entries) > denominator + .00001:
            return None
        return sum(weight for weight, harvest in entries if harvest) / denominator

    @api.model
    def _panel_accounting_rows(self, days, season, species, currency, *, only_costs):
        """The caller must explicitly select the account scope; no stored totals."""
        report = self.env["step.management.actual.cost.report"]
        domain = [("company_id", "=", self.env.company.id),
                  ("center_id.etapa_costo", "in", ("ope", "inver", "cre"))]
        if only_costs:
            domain.append(("account_id.account_type", "in", ("expense", "expense_direct_cost", "expense_depreciation")))
        if days:
            domain.append(("date", ">=", fields.Date.context_today(self) - relativedelta(days=days)))
        if season:
            labels = {token(season.name), token(season.code)} - {""}
            season_accounts = self.env["account.analytic.account"].with_context(active_test=False).search([
                ("root_plan_id", "=", self.env.company.management_actual_season_plan_id.id),
            ]).filtered(lambda account: token(account.name) in labels or token(account.code) in labels)
            domain.append(("season_ids", "in", season_accounts.ids))
        try:
            report.check_access("read")
            source = report.search(domain)
            source.check_access("read")
            if species:
                source = source.filtered(lambda row: row.center_id.especie_id == species
                    if row.center_id.especie_id else token(row.center_id.species) == token(species.name))
            analytic_ids = {int(value.strip()) for row in source for key in (row.analytic_distribution or {})
                            for value in str(key).split(",") if value.strip().isdigit()}
            analytics = {account.id: account for account in self.env["account.analytic.account"].with_context(
                active_test=False).search([("id", "in", list(analytic_ids))])}
            rows = {}
            prefix = currency.name.casefold()
            assert prefix in ("clp", "usd")
            for entry in source:
                center = entry.center_id
                row = rows.setdefault(center.id, {
                    "id": center.id, "name": center.display_name, "hectares": center.hectares,
                    "stage": center.etapa_costo, "maintenance": 0.0, "harvest": 0.0,
                    "amount": 0.0, "available": True,
                })
                share = self._panel_harvest_share(entry, analytics)
                if not entry[prefix + "_available"] or share is None:
                    row["available"] = False
                    continue
                amount = entry["debit_" + prefix] - entry["credit_" + prefix]
                harvest = currency.round(amount * share)
                row["harvest"] += harvest
                row["maintenance"] += amount - harvest
                row["amount"] += amount
            for row in rows.values():
                if not row["available"]:
                    row.update(maintenance=None, harvest=None, amount=None)
            return {"access": True, "rows": list(rows.values())}
        except AccessError:
            # Budget access alone must not grant access to accounting amounts.
            return {"access": False, "rows": []}
