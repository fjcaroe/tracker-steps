import logging
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError
from odoo.tools.misc import format_date

from odoo.addons.step_hr_previred.tools import previred

from ..tools import dt_book


_logger = logging.getLogger(__name__)

# Ticket 20: grupos definidos por posición en el TXT PreviRed consolidado.
WORKER_CONTRIBUTION_FIELDS = (28, 70, 80, 81, 90, 85, 22, 30, 43, 101)
EMPLOYER_CONTRIBUTION_FIELDS = (29, 94, 95, 71, 98, 102)

# Cuántos meses ofrece como máximo el selector de período.
PERIOD_LIMIT = 24


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def _steps_period_label(self, day, short=False):
        """Etiqueta del mes en el idioma del usuario, p. ej. «Julio 2026».

        La forma corta llega abreviada con punto en varios idiomas («Jul.»);
        en las barras de tendencia estorba, así que se retira.
        """
        label = format_date(
            self.env, day, date_format="MMM" if short else "MMMM y"
        ).capitalize()
        return label.rstrip(".") if short else label

    @api.model
    def _steps_default_period(self):
        """Mes anterior.

        El mes en curso casi nunca tiene liquidaciones: se cargan al cierre,
        así que abrir el tablero en el mes corriente muestra todo en cero.
        """
        today = fields.Date.context_today(self)
        return date(today.year, today.month, 1) - relativedelta(months=1)

    @api.model
    def _steps_parse_period(self, period):
        """Convierte «AAAA-MM» en el primer día del mes; si no es válido, usa
        el período por defecto."""
        if period:
            parts = str(period).split("-")
            if len(parts) >= 2:
                try:
                    return date(int(parts[0]), int(parts[1]), 1)
                except ValueError:
                    pass
        return self._steps_default_period()

    def _steps_available_periods(self, company, selected):
        """Meses que ofrece el selector.

        Se listan los meses con liquidaciones para que el usuario no navegue
        entre meses vacíos, más el mes en curso, el anterior y el seleccionado,
        que siempre deben poder elegirse aunque no tengan datos todavía.
        """
        months = set()
        for start, _count in self._read_group(
            [("company_id", "=", company.id)], ["date_from:month"], ["__count"]
        ):
            if start:
                months.add(date(start.year, start.month, 1))

        today = fields.Date.context_today(self)
        current = date(today.year, today.month, 1)
        months.update({current, current - relativedelta(months=1), selected})

        ordered = sorted(months, reverse=True)[:PERIOD_LIMIT]
        if selected not in ordered:
            ordered = sorted(set(ordered) | {selected}, reverse=True)
        return [
            {"value": month.strftime("%Y-%m"), "label": self._steps_period_label(month)}
            for month in ordered
        ]

    @staticmethod
    def _steps_percent(amount, total, digits=1):
        return round(amount * 100.0 / total, digits) if total else 0.0

    @staticmethod
    def _steps_book_values(dataset):
        """Traduce los totales oficiales DT a las magnitudes del panel."""
        totals = dataset.totals
        return {
            "base_salary": totals.get(dt_book.CODE_WAGE, 0),
            "total_income": totals.get(dt_book.CODE_TOTAL_INCOME, 0),
            "net": totals.get(dt_book.CODE_NET, 0),
            "advances": totals.get(dt_book.CODE_ADVANCES, 0),
            "family_allowance": totals.get(dt_book.CODE_FAMILY, 0),
            "available": bool(dataset.lines),
        }

    def _steps_book_summary(self, payslips, company):
        """Totales del Libro DT que alimentan la presentación del panel."""
        result = {
            "base_salary": 0.0,
            "total_income": 0.0,
            "net": 0.0,
            "advances": 0.0,
            "family_allowance": 0.0,
            "available": False,
        }
        if not payslips:
            return result
        extractor = self.env["step.remuneration.book.extractor"]
        present = extractor.payslip_rule_codes(payslips)
        profile, _origin, profile_issues = self.env[
            "step.remuneration.book.profile"].resolve_for(company, present)
        if profile_issues or not profile:
            return result
        lines, issues = extractor.extract_lines(payslips, profile)
        dataset = dt_book.build_dataset(lines, issues=issues)
        if not dataset.lines:
            return result
        result.update(self._steps_book_values(dataset))
        return result

    @staticmethod
    def _steps_row_amount(row, position):
        raw = str(row[position - 1] or "0").strip()
        return int(raw) if raw.lstrip("-").isdigit() else 0

    def _steps_summarize_previred_records(self, records):
        """Agrupa cotizaciones desde las posiciones oficiales del TXT."""
        rows = [row for record in records for row in record.rows]
        worker = sum(
            self._steps_row_amount(row, position)
            for row in rows for position in WORKER_CONTRIBUTION_FIELDS)
        employer = sum(
            self._steps_row_amount(row, position)
            for row in rows for position in EMPLOYER_CONTRIBUTION_FIELDS)
        return {
            "worker": worker,
            "employer": employer,
            "paid": worker + employer,
            "available": bool(rows),
        }

    def _steps_previred_summary(self, company, month_start, month_end):
        """Construye el mismo dataset que el TXT consolidado del período."""
        empty = {"worker": 0, "employer": 0, "paid": 0,
                 "available": False}
        try:
            profile = self.env["step.previred.profile"].default_for(
                company, month_start, strict=False)
            if not profile or profile.availability_error():
                return empty
            dataset = self.env["step.previred.extractor"].build_dataset(
                company=company,
                date_from=month_start,
                date_to=month_end,
                adapter=profile.adapter(),
                states=profile.state_list(),
                allow_without_department=True,
                profile_name=profile.name,
                spec_version=profile.spec_version,
                spec_url=profile.source_url,
                spec_effective_from=profile.effective_from,
            )
            return self._steps_summarize_previred_records(dataset.records)
        except Exception:
            # El panel sigue disponible si el motor PreviRed no responde; la
            # sección de imposiciones queda rotulada como no disponible.
            _logger.exception("No fue posible obtener el resumen PreviRed")
            return empty

    @api.model
    def get_steps_payroll_dashboard(self, period=None):
        if not self.env.user.has_group("hr_payroll.group_hr_payroll_user"):
            raise AccessError(_("No tiene acceso a la información de Nómina."))

        company = self.env.company
        month_start = self._steps_parse_period(period)
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
        legacy_gross = totals["GROSS"] or totals["HAB"]
        legacy_net = totals["NET"] or totals["LIQ"]
        book = self._steps_book_summary(completed, company)
        total_income = book["total_income"] if book["available"] else legacy_gross
        net = book["net"] if book["available"] else legacy_net
        base_salary = book["base_salary"]
        advances = book["advances"]
        contributions = self._steps_previred_summary(
            company, month_start, month_end)
        denominator_without_family = max(
            total_income - book["family_allowance"], 0)
        indicators = {
            "base_salary": self._steps_percent(base_salary, total_income),
            "net": self._steps_percent(net, total_income),
            "advances": self._steps_percent(advances, total_income),
            "employer": self._steps_percent(
                contributions["employer"], total_income),
            "worker": self._steps_percent(
                contributions["worker"], total_income),
            "paid": self._steps_percent(
                contributions["paid"], total_income),
            "insurance_cost": self._steps_percent(
                contributions["employer"], denominator_without_family, 2),
        }

        installed = self.env["ir.module.module"].sudo().search([
            ("name", "=", "l10n_cl_simpledigital_payroll"),
            ("state", "=", "installed"),
        ], limit=1)
        engine = "Steps" if installed else _("Nómina chilena")
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
                "label": self._steps_period_label(start, short=True),
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
            "period": self._steps_period_label(month_start),
            "selected_period": month_start.strftime("%Y-%m"),
            "periods": self._steps_available_periods(company, month_start),
            "currency": company.currency_id.symbol,
            "engine": engine,
            "states": states,
            "total": len(slips),
            "completed": len(completed),
            "employees": employee_count,
            "gross": total_income,
            "net": net,
            "base_salary": base_salary,
            "advances": advances,
            "family_allowance": book["family_allowance"],
            "book_available": book["available"],
            "contributions": contributions,
            "indicators": indicators,
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
