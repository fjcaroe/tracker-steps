from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError


class QualityCheck(models.Model):
    _inherit = "quality.check"

    @api.model
    def get_step_qa_dashboard(self, days=0):
        """Return a compact QA overview while preserving the caller's record rules."""
        days = max(int(days or 0), 0)
        datetime_domain = []
        date_domain = []
        if days:
            start_datetime = fields.Datetime.now() - relativedelta(days=days)
            datetime_domain = [("create_date", ">=", fields.Datetime.to_string(start_datetime))]
            date_domain = [("create_date", ">=", fields.Datetime.to_string(start_datetime))]

        total = self.search_count(datetime_domain)
        passed = self.search_count(datetime_domain + [("quality_state", "=", "pass")])
        failed = self.search_count(datetime_domain + [("quality_state", "=", "fail")])
        pending = self.search_count(datetime_domain + [("quality_state", "=", "none")])
        evaluated = passed + failed

        alert_model = self.env["quality.alert"]
        open_alerts = alert_model.search_count(
            datetime_domain + [("stage_id.done", "=", False)]
        )
        critical_alerts = alert_model.search_count(
            datetime_domain + [("stage_id.done", "=", False), ("priority", "=", "3")]
        )

        point_model = self.env["quality.point"]
        active_points = point_model.search_count([("active", "=", True)])
        teams = self.env["quality.alert.team"].search_count([])

        recent_checks = []
        for check in self.search(datetime_domain, order="control_date desc, create_date desc", limit=8):
            recent_checks.append({
                "id": check.id,
                "name": check.name or check.title or "Control sin referencia",
                "title": check.title or check.point_id.title or "Control de calidad",
                "state": check.quality_state or "none",
                "date": fields.Datetime.to_string(check.control_date or check.create_date),
                "product": check.product_id.display_name or "Sin producto",
                "team": check.team_id.display_name or "Sin equipo",
            })

        recent_alerts = []
        for alert in alert_model.search(
            datetime_domain + [("stage_id.done", "=", False)],
            order="priority desc, create_date desc",
            limit=5,
        ):
            recent_alerts.append({
                "id": alert.id,
                "name": alert.name or "Alerta de calidad",
                "title": alert.title or alert.product_tmpl_id.display_name or "Revisión pendiente",
                "stage": alert.stage_id.display_name or "Sin etapa",
                "priority": alert.priority or "0",
                "responsible": alert.user_id.display_name or "Sin responsable",
            })

        inspections = self._step_qa_inspection_summary(date_domain)
        advisors = self._step_qa_advisor_summary(date_domain)

        return {
            "period_days": days,
            "checks": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "pending": pending,
                "pass_rate": round((passed / evaluated) * 100, 1) if evaluated else 0.0,
            },
            "open_alerts": open_alerts,
            "critical_alerts": critical_alerts,
            "active_points": active_points,
            "teams": teams,
            "inspections": inspections,
            "advisors": advisors,
            "recent_checks": recent_checks,
            "recent_alerts": recent_alerts,
        }

    @api.model
    def _step_qa_inspection_summary(self, period_domain):
        if "x_inspecciones_interna" not in self.env:
            return {"available": False, "total": 0, "created": 0, "executed": 0, "approved": 0, "overdue": 0, "recent": []}
        model = self.env["x_inspecciones_interna"]
        try:
            total = model.search_count(period_domain)
            created = model.search_count(period_domain + [("x_studio_selection_field_6l2_1jhuo823d", "=", "status1")])
            executed = model.search_count(period_domain + [("x_studio_selection_field_6l2_1jhuo823d", "=", "status2")])
            approved = model.search_count(period_domain + [("x_studio_selection_field_6l2_1jhuo823d", "=", "status3")])
            overdue = model.search_count(period_domain + [
                ("x_studio_selection_field_6l2_1jhuo823d", "=", "status1"),
                ("x_studio_fecha_a_ejecutar", "<", fields.Date.context_today(self)),
            ])
            recent = []
            for record in model.search(period_domain, order="x_studio_fecha_a_ejecutar desc, create_date desc", limit=6):
                recent.append({
                    "id": record.id,
                    "name": record.x_name or "Inspección interna",
                    "state": record.x_studio_selection_field_6l2_1jhuo823d or "status1",
                    "date": fields.Date.to_string(record.x_studio_fecha_a_ejecutar or record.x_studio_fecha),
                    "farm": record.x_studio_fundo.display_name or "Sin fundo",
                    "responsible": record.x_studio_asignado_a.display_name or record.x_studio_responsable.display_name or "Sin asignar",
                })
            return {
                "available": True,
                "total": total,
                "created": created,
                "executed": executed,
                "approved": approved,
                "overdue": overdue,
                "recent": recent,
            }
        except AccessError:
            return {"available": False, "total": 0, "created": 0, "executed": 0, "approved": 0, "overdue": 0, "recent": []}

    @api.model
    def _step_qa_advisor_summary(self, period_domain):
        if "x_asesor_externo" not in self.env:
            return {"available": False, "total": 0, "pending": 0}
        model = self.env["x_asesor_externo"]
        try:
            return {
                "available": True,
                "total": model.search_count(period_domain),
                "pending": model.search_count(period_domain + [
                    ("x_studio_selection_field_9fu_1jhjpstuu", "=", "status1")
                ]),
            }
        except AccessError:
            return {"available": False, "total": 0, "pending": 0}
