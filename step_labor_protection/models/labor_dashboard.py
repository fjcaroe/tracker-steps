from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError


class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model
    def get_step_labor_dashboard(self, days=0):
        days = max(int(days or 0), 0)
        start = fields.Datetime.now() - relativedelta(days=days) if days else False
        date_domain = [("create_date", ">=", fields.Datetime.to_string(start))] if start else []

        data = {
            "period_days": days,
            "courses": self._step_labor_studio_summary("x_inducciones_y_cursos", date_domain),
            "epp": self._step_labor_studio_summary("x_entrega_epp", date_domain),
            "accidents": self._step_labor_studio_summary("x_accidentes_laborales", date_domain),
            "risks": self._step_labor_studio_summary("x_riesgos_laborales", []),
            "protocols": {"total": 0, "active": 0, "review": 0},
            "karin": {"allowed": False, "total": 0, "open": 0, "overdue": 0, "safeguards": 0},
        }

        protocol_model = self.env["step.labor.protocol"]
        try:
            review_limit = fields.Date.context_today(self) + relativedelta(days=30)
            data["protocols"] = {
                "total": protocol_model.search_count([]),
                "active": protocol_model.search_count([("state", "=", "active")]),
                "review": protocol_model.search_count([
                    ("state", "=", "active"), ("review_date", "<=", review_limit)
                ]),
            }
        except AccessError:
            pass

        if self.env.user.has_group("step_labor_protection.group_labor_confidential") or self.env.user.has_group("hr.group_hr_manager"):
            case_model = self.env["step.labor.karin.case"]
            case_domain = [("report_date", ">=", fields.Date.to_string(start.date()))] if start else []
            data["karin"] = {
                "allowed": True,
                "total": case_model.search_count(case_domain),
                "open": case_model.search_count(case_domain + [("state", "not in", ["closed", "discarded"])]),
                "overdue": case_model.search_count(case_domain + [("deadline_status", "=", "overdue")]),
                "safeguards": self.env["step.labor.karin.safeguard"].search_count(
                    [("case_id.report_date", ">=", fields.Date.to_string(start.date()))] + [("state", "=", "active")]
                    if start else [("state", "=", "active")]
                ),
            }

        return data

    @api.model
    def _step_labor_studio_summary(self, model_name, domain):
        if model_name not in self.env:
            return {"available": False, "total": 0}
        try:
            return {"available": True, "total": self.env[model_name].search_count(domain)}
        except AccessError:
            return {"available": False, "total": 0}
