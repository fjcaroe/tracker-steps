from odoo import models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def _get_worked_day_lines_values(self, domain=None):
        lines = super()._get_worked_day_lines_values(domain=domain)
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
