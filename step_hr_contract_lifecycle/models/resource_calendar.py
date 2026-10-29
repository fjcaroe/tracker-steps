"""Contractual weekly hours from the actual installed calendar provider.

Community's resource module exposes global attendance and duration APIs, but
does not expose the native payroll hours_per_week field. Do not add a second
stored value or derive a week from a default eight-hour day.
"""
from odoo import _, models
from odoo.exceptions import UserError


class ResourceCalendar(models.Model):
    _inherit = "resource.calendar"

    def _steps_contract_weekly_hours(self):
        self.ensure_one()
        self.check_access("read")
        rows = self.attendance_ids.filtered(lambda row: not row.display_type and row.day_period != "lunch")
        if any(row.date_from or row.date_to or row.resource_id for row in rows):
            raise UserError(_("La jornada tiene fechas o asignaciones individuales. Revise la referencia contractual antes de resumirla por semana."))
        attendances = self._get_global_attendances()
        if self.two_weeks_calendar and any(row.week_type not in ("0", "1") for row in attendances):
            raise UserError(_("Complete la semana original de cada tramo del calendario de dos semanas."))
        if "hours_per_week" in self._fields:
            # Keep the actual native provider's contractual value authoritative.
            return self.hours_per_week
        if self.flexible_hours:
            raise UserError(_("La jornada flexible requiere una referencia original de horas semanales; no se deduce de la jornada de la compañía."))
        # duration_hours is computed by the official resource attendance API.
        # A two-week calendar defines a full fourteen-day cycle, including days
        # without attendance. Average that actual cycle, without daily defaults.
        return sum(attendances.mapped("duration_hours")) / (2 if self.two_weeks_calendar else 1)
