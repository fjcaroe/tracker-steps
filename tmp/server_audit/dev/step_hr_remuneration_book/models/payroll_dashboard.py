from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    @api.model
    def get_steps_payroll_dashboard(self):
        if not self.env.user.has_group("hr_payroll.group_hr_payroll_user"):
            raise AccessError(_("No tiene acceso a la información de Nómina."))

        company = self.env.company
        today = fields.Date.context_today(self)
        month_start = date(today.year, today.month, 1)
        month_end = month_start + relativedelta(months=1, days=-1)
        base_domain = [
            ("company_id", "=", company.id),
            ("date_from", "<=", month_end),
            ("date_to", ">=", month_start),
        ]
        slips = self.search(base_domain)
        states = {state: 0 for state in ("draft", "verify", "done", "paid", "cancel")}
        for state, count in self._read_group(base_domain, ["state"], ["__count"]):
            states[state] = count

        completed = slips.filtered(lambda slip: slip.state in ("done", "paid"))
        employee_count = len(set(completed.mapped("employee_id").ids))
        missing_identification = len(completed.employee_id.filtered(lambda employee: not employee.identification_id))

        rule_codes = {"GROSS", "NET", "HAB", "LIQ"}
        totals = defaultdict_float()
        if completed:
            grouped = self.env["hr.payslip.line"]._read_group(
                [("slip_id", "in", completed.ids), ("code", "in", list(rule_codes))],
                ["code"],
                ["total:sum"],
            )
            for code, amount in grouped:
                totals[code] = amount or 0.0
        gross = totals["GROSS"] or totals["HAB"]
        net = totals["NET"] or totals["LIQ"]

        installed = self.env["ir.module.module"].sudo().search([
            ("name", "=", "l10n_cl_simpledigital_payroll"),
            ("state", "=", "installed"),
        ], limit=1)
        engine = "SimpleDigital" if installed else _("Nómina chilena")
        profile = company.remuneration_book_profile_id

        batches = self.env["hr.payslip.run"].search([
            ("company_id", "=", company.id),
        ], order="date_end desc, id desc", limit=5)
        recent_batches = []
        for batch in batches:
            batch_slips = batch.slip_ids
            recent_batches.append({
                "id": batch.id,
                "name": batch.name,
                "date_start": fields.Date.to_string(batch.date_start),
                "date_end": fields.Date.to_string(batch.date_end),
                "count": len(batch_slips),
                "done": len(batch_slips.filtered(lambda slip: slip.state in ("done", "paid"))),
            })

        trend = []
        for offset in range(5, -1, -1):
            start = month_start - relativedelta(months=offset)
            end = start + relativedelta(months=1, days=-1)
            domain = [
                ("company_id", "=", company.id),
                ("date_from", "<=", end),
                ("date_to", ">=", start),
                ("state", "in", ("done", "paid")),
            ]
            trend.append({
                "label": start.strftime("%b").capitalize(),
                "count": self.search_count(domain),
            })
        max_trend = max((item["count"] for item in trend), default=1) or 1
        for item in trend:
            item["percent"] = round(item["count"] * 100.0 / max_trend, 1)

        can_full_book = self.env.user.has_group(
            "step_hr_remuneration_book.group_remuneration_book_full"
        )
        return {
            "company": company.display_name,
            "period": month_start.strftime("%B %Y").capitalize(),
            "currency": company.currency_id.symbol,
            "engine": engine,
            "states": states,
            "total": len(slips),
            "completed": len(completed),
            "employees": employee_count,
            "gross": gross,
            "net": net,
            "missing_identification": missing_identification,
            "profile": profile.display_name if profile else _("Sin perfil asignado"),
            "profile_state": profile.state if profile else "missing",
            "can_full_book": can_full_book,
            "recent_batches": recent_batches,
            "trend": trend,
        }


def defaultdict_float():
    """Diccionario pequeño sin importar collections en cada llamada RPC."""
    return {"GROSS": 0.0, "NET": 0.0, "HAB": 0.0, "LIQ": 0.0}
