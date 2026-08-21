from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError


class BpaIrrigationDashboard(models.Model):
    _inherit = "x_riego_y_fertilizacio"

    @api.model
    def get_step_bpa_dashboard(self, days=0):
        """Return a compact overview while preserving record rules."""
        days = max(int(days or 0), 0)
        domain = []
        if days:
            start = fields.Datetime.now() - relativedelta(days=days)
            domain = [("create_date", ">=", fields.Datetime.to_string(start))]

        irrigation = self.env["x_riego_y_fertilizacio"]
        application = self.env["x_aplicacion_foliar"]
        monitoring = self.env["x_monitoreo_agricola"]
        sectors = self.env["x_sector_de_riego"]

        try:
            irrigation_records = irrigation.search(domain)
            application_records = application.search(domain)
            monitoring_records = monitoring.search(domain)

            irrigated_hectares = sum(irrigation_records.mapped("x_studio_hectreas_a_regar"))
            mixture_liters = sum(irrigation_records.mapped("x_studio_litros_mezcla"))
            applied_hectares = sum(application_records.mapped("x_studio_total_hectreas"))
            application_cost = sum(application_records.mapped("x_studio_costo_total_aplicacin"))

            return {
                "period_days": days,
                "irrigation": {
                    "total": len(irrigation_records),
                    "hectares": irrigated_hectares,
                    "mixture_liters": mixture_liters,
                    "only_water": irrigation.search_count(domain + [("x_studio_slo_riego", "=", True)]),
                },
                "applications": {
                    "total": len(application_records),
                    "hectares": applied_hectares,
                    "cost": application_cost,
                },
                "monitoring": {"total": len(monitoring_records)},
                "sectors": {
                    "total": sectors.search_count([]),
                    "hectares": sum(sectors.search([]).mapped("x_studio_total_hs")),
                },
                "recent": self._step_bpa_recent(irrigation, application, monitoring, domain),
            }
        except AccessError:
            return {
                "period_days": days,
                "unavailable": True,
                "irrigation": {"total": 0, "hectares": 0, "mixture_liters": 0, "only_water": 0},
                "applications": {"total": 0, "hectares": 0, "cost": 0},
                "monitoring": {"total": 0},
                "sectors": {"total": 0, "hectares": 0},
                "recent": [],
            }

    @api.model
    def _step_bpa_recent(self, irrigation, application, monitoring, domain):
        records = []
        definitions = (
            (irrigation, "x_studio_fecha", "Riego y fertilización", "fa-tint"),
            (application, "x_studio_fecha", "Aplicación foliar", "fa-leaf"),
            (monitoring, "x_studio_fecha", "Monitoreo agrícola", "fa-binoculars"),
        )
        for model, date_field, label, icon in definitions:
            for record in model.search(domain, order=f"{date_field} desc, create_date desc", limit=5):
                farm = getattr(record, "x_studio_fundo", False)
                responsible = (
                    getattr(record, "x_studio_responsaable", False)
                    or getattr(record, "x_studio_responsable", False)
                    or getattr(record, "x_studio_aprueba", False)
                )
                records.append({
                    "id": record.id,
                    "model": model._name,
                    "name": record.x_name or label,
                    "kind": label,
                    "icon": icon,
                    "date": fields.Date.to_string(getattr(record, date_field, False)),
                    "farm": farm.display_name if farm else "Sin fundo",
                    "responsible": responsible.display_name if responsible else "Sin responsable",
                    "create_date": fields.Datetime.to_string(record.create_date),
                })
        records.sort(key=lambda item: (item["date"] or "", item["create_date"] or ""), reverse=True)
        return records[:10]
