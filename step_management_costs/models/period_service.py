"""Servicio de períodos: temporada, meses y semanas ISO-8601 (plan D04).

`step.management.period.service` es un `AbstractModel` sin tabla; expone
utilidades deterministas que consumen la planificación semanal y el plan de
cosecha.

Supuestos que requieren validación de Operaciones (D04) — cambiarlos es un
cambio acotado a este archivo:

  F4-A1. Temporada = 12 meses desde el mes de inicio configurable
         (`ir.config_parameter step_management_costs.season_start_month`,
         valor por defecto 5 = mayo). «2026/2027» ⇒ 2026-05-01 … 2027-04-30.
  F4-A2. Semana = ISO-8601 (lunes a domingo). Se admite la semana 53.
  F4-A3. Reparto de una cantidad mensual entre sus semanas: a prorrata de los
         **días naturales** de cada semana que caen dentro del mes y del rango
         de la temporada (no días hábiles). El residuo de redondeo se asigna a
         la última semana del mes (misma política determinista que las
         distribuciones de estimación).
  F4-A4. La distribución cubre **todas** las semanas de la temporada (C3): las
         semanas sin cantidad se devuelven en cero, no se omiten.
"""

import re
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

MONTH_KEY_TO_NUMBER = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


class StepManagementPeriodService(models.AbstractModel):
    _name = "step.management.period.service"
    _description = "Servicio de períodos (temporada, meses, semanas ISO)"

    @api.model
    def _season_start_month(self):
        raw = self.env["ir.config_parameter"].sudo().get_param(
            "step_management_costs.season_start_month", "5"
        )
        try:
            month = int(raw)
        except (TypeError, ValueError):
            month = 5
        return month if 1 <= month <= 12 else 5

    @api.model
    def season_bounds(self, season):
        """«2026/2027» o «2026» → (primer día, último día) de la temporada."""
        years = [int(v) for v in re.findall(r"\b\d{4}\b", season or "")]
        if years:
            base_year = years[0]
        else:
            base_year = fields.Date.context_today(self).year
        start_month = self._season_start_month()
        start = date(base_year, start_month, 1)
        end = start + relativedelta(years=1) - relativedelta(days=1)
        return start, end

    @api.model
    def season_of_date(self, a_date):
        """Inversa de `season_bounds`: dada una fecha, la temporada
        «AAAA/AAAA+1» a la que pertenece según el mes de inicio configurable
        (F4-A1). Usado por el Corte V2 F para ubicar un apunte contable real
        (que sólo trae fecha) dentro de una temporada, sin inventar un
        maestro de temporadas (D03 sigue abierta)."""
        a_date = fields.Date.to_date(a_date)
        start_month = self._season_start_month()
        base_year = a_date.year if a_date.month >= start_month else a_date.year - 1
        return "%d/%d" % (base_year, base_year + 1)

    @api.model
    def iso_weeks(self, date_from, date_to):
        """Semanas ISO que intersectan [date_from, date_to], en orden.

        Cada dict: iso_year, iso_week, label ('W01'..'W53'), monday, sunday,
        days_in_range (1..7)."""
        date_from = fields.Date.to_date(date_from)
        date_to = fields.Date.to_date(date_to)
        weeks = []
        cursor = date_from - timedelta(days=date_from.weekday())  # lunes
        while cursor <= date_to:
            monday = cursor
            sunday = cursor + timedelta(days=6)
            lo = max(monday, date_from)
            hi = min(sunday, date_to)
            iso_year, iso_week, _weekday = monday.isocalendar()
            weeks.append({
                "iso_year": iso_year,
                "iso_week": iso_week,
                "label": "W%02d" % iso_week,
                "monday": monday,
                "sunday": sunday,
                "days_in_range": (hi - lo).days + 1,
            })
            cursor += timedelta(days=7)
        return weeks

    @api.model
    def _normalize_month_values(self, month_values):
        normalized = {}
        for key, qty in (month_values or {}).items():
            if isinstance(key, str):
                number = MONTH_KEY_TO_NUMBER.get(key.strip().lower())
            else:
                number = int(key)
            if not number or not 1 <= number <= 12:
                continue
            normalized[number] = normalized.get(number, 0.0) + (qty or 0.0)
        return normalized

    @api.model
    def distribute_monthly_to_weeks(self, season, month_values, rounding=0.0001):
        """Reparte cantidades mensuales entre las semanas ISO de la temporada.

        `month_values`: {mes → cantidad}, con el mes como número (1-12) o clave
        ('jan'..'dec'). Devuelve una lista ordenada de dicts
        {label, iso_year, iso_week, monday, sunday, quantity} que cubre TODAS
        las semanas de la temporada; cada mes concilia exactamente con la suma
        de sus semanas (residuo a la última semana del mes)."""
        from odoo.tools.float_utils import float_round

        start, end = self.season_bounds(season)
        weeks = self.iso_weeks(start, end)
        totals = [0.0] * len(weeks)
        month_values = self._normalize_month_values(month_values)

        for month_number, quantity in month_values.items():
            if not quantity:
                continue
            # días de cada semana que caen en este mes y dentro de la temporada
            days_by_week = []
            for index, week in enumerate(weeks):
                days = 0
                day = week["monday"]
                while day <= week["sunday"]:
                    if start <= day <= end and day.month == month_number:
                        days += 1
                    day += timedelta(days=1)
                if days:
                    days_by_week.append((index, days))
            total_days = sum(days for _i, days in days_by_week)
            if not total_days:
                continue
            allocated = 0.0
            for position, (index, days) in enumerate(days_by_week):
                if position < len(days_by_week) - 1:
                    part = float_round(
                        quantity * days / total_days, precision_rounding=rounding
                    )
                    allocated = float_round(
                        allocated + part, precision_rounding=rounding
                    )
                else:
                    part = float_round(
                        quantity - allocated, precision_rounding=rounding
                    )
                totals[index] = float_round(
                    totals[index] + part, precision_rounding=rounding
                )

        result = []
        for index, week in enumerate(weeks):
            result.append(dict(week, quantity=totals[index]))
        return result

    @api.model
    def week_of_season(self, season, week_number):
        """Ubica el número de semana ISO (1-53) dentro de la temporada.

        Devuelve {label, iso_year, iso_week, monday, sunday, days_in_range,
        month, year, index} o False si ese número no cae en la temporada."""
        if not week_number:
            return False
        start, end = self.season_bounds(season)
        for index, week in enumerate(self.iso_weeks(start, end), start=1):
            if week["iso_week"] == week_number:
                return dict(
                    week, month=week["monday"].month,
                    year=week["monday"].year, index=index,
                )
        return False
