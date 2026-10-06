from datetime import datetime, time

from odoo import fields, models

LATE_CODE = "LEAVECL131"
HOURS_PER_DAY = 8.0


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def _get_worked_day_lines_values(self, domain=None):
        lines = super()._get_worked_day_lines_values(domain=domain)
        lines = self._step_contract_days_lines(lines)
        return self._step_deduct_late_hours(lines)

    def _step_late_hours(self):
        """Horas de atraso (entradas LEAVECL131) del trabajador en el período."""
        self.ensure_one()
        start = datetime.combine(fields.Date.to_date(self.date_from), time.min)
        end = datetime.combine(fields.Date.to_date(self.date_to), time.max)
        entries = self.env["hr.work.entry"].search([
            ("employee_id", "=", self.employee_id.id),
            ("work_entry_type_id.code", "=", LATE_CODE),
            ("state", "!=", "cancelled"),
            ("date_start", ">=", start),
            ("date_start", "<=", end),
        ])
        return sum(entries.mapped("duration"))

    def _step_deduct_late_hours(self, lines):
        """Descuenta del sueldo base las horas no trabajadas por atrasos.

        El motor del proveedor arma la asistencia como 30 días menos licencias,
        faltas y vacaciones, e ignora LEAVECL131. Las horas se convierten a días
        (8 h = 1 día, convención del motor) y se restan de WORK100, proporcional
        al importe ya calculado. No cambia los días previsionales (Previred solo
        resta licencias/faltas/etc.).
        """
        if self.struct_id.name != "Nómina Chile" or not self.employee_id:
            return lines
        late_hours = self._step_late_hours()
        if late_hours <= 0:
            return lines
        entry_types = self.env["hr.work.entry.type"]
        by_code = {}
        for line in lines:
            by_code.setdefault(entry_types.browse(line["work_entry_type_id"]).code, line)
        attendance = by_code.get("WORK100")
        late_days = late_hours / HOURS_PER_DAY
        old_days = attendance.get("number_of_days", 0.0) if attendance else 0.0
        if attendance is not None and old_days > 0:
            new_days = max(old_days - late_days, 0.0)
            old_amount = attendance.get("amount") or self.contract_id.wage / 30.0 * old_days
            attendance.update({
                "number_of_days": new_days,
                "number_of_hours": new_days * HOURS_PER_DAY,
                "amount": old_amount * new_days / old_days,
            })
        late_line = by_code.get(LATE_CODE)
        if late_line is None:
            late_type = entry_types.search([("code", "=", LATE_CODE)], limit=1)
            if late_type:
                late_line = {"sequence": late_type.sequence, "work_entry_type_id": late_type.id}
                lines.append(late_line)
        if late_line is not None:
            late_line.update({
                "number_of_days": late_days,
                "number_of_hours": late_hours,
                "amount": 0.0,
            })
        return lines

    def _step_contract_days_lines(self, lines):
        contract = self.contract_id
        if not (
            self.struct_id.name == "Nómina Chile"
            and contract.date_start
            and contract.date_end
            and self.date_from < contract.date_start <= contract.date_end < self.date_to
        ):
            return lines

        # SimpleDigital already bounds the base to the contract's actual
        # duration on a mid-period exit. Subtracting pre-entry days again
        # understates attendance (e.g. a 9-day contract becomes 2 days).
        # Rebuild attendance from that bounded duration and the normalized
        # leave lines, so absences still work when the old result hit zero.
        entry_types = self.env["hr.work.entry.type"]
        leave_codes = {"LIC", "LEAVECL130", "FALT", "LEAVECL120"}
        leave_days = sum(
            line.get("number_of_days", 0.0)
            for line in lines
            if entry_types.browse(line["work_entry_type_id"]).code in leave_codes
        )
        days = max((contract.date_end - contract.date_start).days + 1 - leave_days, 0.0)
        divisor = 31.0 if (self.date_to - self.date_from).days + 1 == 31 else 30.0
        attendance = next(
            (line for line in lines
             if entry_types.browse(line["work_entry_type_id"]).code == "WORK100"),
            None,
        )
        if attendance is None and days:
            work_type = entry_types.search([("code", "=", "WORK100")], limit=1)
            if work_type:
                attendance = {"sequence": work_type.sequence, "work_entry_type_id": work_type.id}
                lines.append(attendance)
        if attendance is not None:
            attendance.update({
                "number_of_days": days,
                "number_of_hours": days * 8,
                "amount": contract.wage / divisor * days,
            })
        return lines
