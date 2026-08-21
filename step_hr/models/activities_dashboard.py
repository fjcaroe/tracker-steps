# -*- coding: utf-8 -*-

from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class HrSalaryCustomActivitiesDashboard(models.Model):
    _inherit = "hr.salary.custom"

    @api.model
    def get_activities_dashboard_data(self, days=30):
        """Return an operational summary without changing transactional flows."""
        days = int(30 if days is None else days)
        days = 0 if days == 0 else max(7, min(days, 365))
        salary_domain = [("company_id", "=", self.env.company.id)]
        tarja_domain = [("company_id", "=", self.env.company.id)]
        movi_domain = [("company_id", "=", self.env.company.id)]
        if days:
            date_from = fields.Date.today() - timedelta(days=days)
            salary_domain.append(("date", ">=", fields.Date.to_string(date_from)))
            tarja_domain.append(("date", ">=", fields.Date.to_string(date_from)))
            movi_domain.append(("date", ">=", fields.Datetime.to_string(date_from)))

        salaries = self.search(salary_domain)
        salary_ids = salaries.ids
        own_line_domain = [("salary_id", "in", salary_ids)]
        contractor_line_domain = [("salary_id", "in", salary_ids)]
        own_totals = self.env["hr.salary.custom.line"].read_group(
            own_line_domain, ["hours:sum"], []
        )
        contractor_totals = self.env["hr.salary.contract.line"].read_group(
            contractor_line_domain, ["hours:sum"], []
        )
        own_totals = own_totals[0] if own_totals else {}
        contractor_totals = contractor_totals[0] if contractor_totals else {}
        own_workers = self.env["hr.salary.custom.line"].read_group(
            own_line_domain + [("employee_id", "!=", False)],
            ["employee_id"],
            ["employee_id"],
            lazy=False,
        )
        contractor_workers = self.env["hr.salary.contract.line"].read_group(
            contractor_line_domain + [("employee_id", "!=", False)],
            ["employee_id"],
            ["employee_id"],
            lazy=False,
        )

        tarjas = self.env["step.tarja"].search(tarja_domain)
        task_totals = self.env["step.tarja.line"].read_group(
            [("tarja_id", "in", tarjas.ids)],
            ["hrs_total:sum", "total_trato:sum", "cost_empresa:sum"],
            [],
        )
        task_totals = task_totals[0] if task_totals else {}

        state_counts = {
            state: self.search_count(salary_domain + [("state", "=", state)])
            for state in ("draft", "progress", "done")
        }
        type_counts = {
            group_type: self.search_count(salary_domain + [("group_type", "=", group_type)])
            for group_type in ("propio", "contratista")
        }
        tarja_types = {
            tarja_type: self.env["step.tarja"].search_count(
                tarja_domain + [("tarja_type", "=", tarja_type)]
            )
            for tarja_type in ("propio", "contratista")
        }

        fundo_groups = self.read_group(
            salary_domain + [("fundo_id", "!=", False)],
            ["fundo_id"],
            ["fundo_id"],
        )
        fundo_groups = sorted(fundo_groups, key=lambda group: group["__count"], reverse=True)[:5]
        max_fundo = max((group["__count"] for group in fundo_groups), default=1)

        latest_salary = self.search(
            [("company_id", "=", self.env.company.id), ("date", "!=", False)],
            order="date desc, id desc",
            limit=1,
        )
        trend_anchor = latest_salary.date if days == 0 and latest_salary else fields.Date.today()
        month_start = trend_anchor.replace(day=1)
        trend = []
        for offset in range(5, -1, -1):
            start = month_start - relativedelta(months=offset)
            end = start + relativedelta(months=1)
            month_domain = [
                ("company_id", "=", self.env.company.id),
                ("date", ">=", fields.Date.to_string(start)),
                ("date", "<", fields.Date.to_string(end)),
            ]
            month_salaries = self.search(month_domain)
            month_hours = self.env["hr.salary.custom.line"].read_group(
                [("salary_id", "in", month_salaries.ids)], ["hours:sum"], []
            )
            month_hours_contractor = self.env["hr.salary.contract.line"].read_group(
                [("salary_id", "in", month_salaries.ids)], ["hours:sum"], []
            )
            hours = (month_hours[0].get("hours", 0.0) if month_hours else 0.0) + (
                month_hours_contractor[0].get("hours", 0.0) if month_hours_contractor else 0.0
            )
            trend.append({
                "label": start.strftime("%b").upper(),
                "records": len(month_salaries),
                "hours": hours,
            })
        max_trend = max((item["hours"] for item in trend), default=1.0) or 1.0
        for item in trend:
            item["percent"] = round((item["hours"] / max_trend) * 100, 1)

        recent = self.search(salary_domain, order="date desc, id desc", limit=7)
        selection_state = dict(self._fields["state"].selection)
        selection_type = dict(self._fields["group_type"].selection)
        total_hours = (own_totals.get("hours", 0.0) or 0.0) + (
            contractor_totals.get("hours", 0.0) or 0.0
        )

        return {
            "company_name": self.env.company.display_name,
            "days": days,
            "period_label": "Todo el histórico" if days == 0 else f"Últimos {days} días",
            "kpis": {
                "crews": len(salaries),
                "workers": len(own_workers) + len(contractor_workers),
                "hours": total_hours,
                "tasks": len(tarjas),
                "variable_pay": task_totals.get("total_trato", 0.0) or 0.0,
                "company_cost": task_totals.get("cost_empresa", 0.0) or 0.0,
                "mobilizations": self.env["step.movi.registry"].search_count(movi_domain),
            },
            "states": state_counts,
            "types": type_counts,
            "tarja_types": tarja_types,
            "trend": trend,
            "fundos": [{
                "id": group["fundo_id"][0],
                "name": group["fundo_id"][1],
                "count": group["__count"],
                "percent": round((group["__count"] / max_fundo) * 100, 1),
            } for group in fundo_groups],
            "recent": [{
                "id": record.id,
                "name": record.display_name,
                "date": fields.Date.to_string(record.date) if record.date else False,
                "fundo": record.fundo_id.display_name or "Sin fundo",
                "supervisor": record.employee_id.display_name or record.responsable_id.display_name or "Sin responsable",
                "type": record.group_type or "propio",
                "type_label": selection_type.get(record.group_type, "Sin tipo"),
                "state": record.state or "draft",
                "state_label": selection_state.get(record.state, "Nuevo"),
                "workers": len(record.salary_line) + len(record.contract_line),
            } for record in recent],
        }
