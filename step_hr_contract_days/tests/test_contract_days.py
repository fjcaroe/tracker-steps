from datetime import date
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestContractDays(TransactionCase):
    def test_contract_boundaries_and_absences(self):
        work = self.env["hr.work.entry.type"].search([("code", "=", "WORK100")], limit=1)
        self.assertTrue(work)
        leave = self.env["hr.work.entry.type"].search([("code", "=", "FALT")], limit=1)
        if not leave:
            leave = self.env["hr.work.entry.type"].create({"name": "Test absence", "code": "FALT", "is_leave": True})
        structure = self.env["hr.payroll.structure"].new({"name": "Nómina Chile"})
        provider = next(
            cls for cls in type(self.env["hr.payslip"]).__mro__
            if cls.__module__ == "odoo.addons.l10n_cl_simpledigital_payroll.models.hr_payslip"
            and "_get_worked_day_lines_values" in cls.__dict__
        )
        # month, last day, entry, exit, absence, old attendance, corrected attendance
        cases = [
            (9, 30, 8, 16, 0, 2, 9),
            (9, 30, 8, 16, 4, 0, 5),
            (9, 30, 8, 16, 9, 0, 0),
            (9, 30, 8, 16, 12, 0, 0),
            (9, 30, 20, 21, 0, 0, 2),
            (9, 30, 8, 30, 0, 23, 23),
            (9, 30, 1, 16, 0, 16, 16),
            (9, 30, 1, 30, 0, 30, 30),
            (8, 31, 8, 16, 0, 2, 9),
        ]
        for month, last, start, end, absence, old, expected in cases:
            for existing_line in (True, False):
                # Unaffected cases preserve the provider output verbatim.
                if not existing_line and not (1 < start <= end < last):
                    continue
                with self.subTest(month=month, start=start, end=end, absence=absence, existing=existing_line):
                    contract = self.env["hr.contract"].new({
                        "date_start": date(2026, month, start),
                        "date_end": date(2026, month, end), "wage": 600000,
                    })
                    slip = self.env["hr.payslip"].new({
                        "contract_id": contract, "struct_id": structure,
                        "date_from": date(2026, month, 1), "date_to": date(2026, month, last),
                    })
                    source = []
                    if existing_line:
                        source.append({"work_entry_type_id": work.id, "number_of_days": old})
                    if absence:
                        source.append({"work_entry_type_id": leave.id, "number_of_days": absence})
                    with patch.object(provider, "_get_worked_day_lines_values", return_value=source):
                        lines = slip._get_worked_day_lines_values()
                    attendance = [line for line in lines if line["work_entry_type_id"] == work.id]
                    self.assertEqual(sum(line["number_of_days"] for line in attendance), expected)
                    if attendance and 1 < start <= end < last:
                        self.assertEqual(attendance[0]["number_of_hours"], expected * 8)
                        self.assertAlmostEqual(attendance[0]["amount"], 600000 / (31 if last == 31 else 30) * expected)

    def test_late_hours_are_deducted_from_attendance(self):
        """T47: 2.8 h de atraso sobre sueldo 553.553 -> 29,65 días, base 547.095."""
        entry_types = self.env["hr.work.entry.type"]
        work = entry_types.search([("code", "=", "WORK100")], limit=1)
        late = entry_types.search([("code", "=", "LEAVECL131")], limit=1)
        if not late:
            late = entry_types.create({"name": "Test atraso", "code": "LEAVECL131", "is_leave": True})
        structure = self.env["hr.payroll.structure"].new({"name": "Nómina Chile"})
        provider = next(
            cls for cls in type(self.env["hr.payslip"]).__mro__
            if cls.__module__ == "odoo.addons.l10n_cl_simpledigital_payroll.models.hr_payslip"
            and "_get_worked_day_lines_values" in cls.__dict__
        )
        wage = 553553
        slip = self.env["hr.payslip"].new({
            "contract_id": self.env["hr.contract"].new({"wage": wage}),
            "struct_id": structure,
            "employee_id": self.env["hr.employee"].new({"name": "Test"}),
            "date_from": date(2026, 9, 1), "date_to": date(2026, 9, 30),
        })
        cls = type(self.env["hr.payslip"])
        for hours, extra_line, exp_days in ((2.8, False, 29.65), (2.8, True, 29.65), (0.0, False, 30.0), (400.0, False, 0.0)):
            with self.subTest(hours=hours, extra_line=extra_line):
                source = [{"work_entry_type_id": work.id, "number_of_days": 30.0,
                           "number_of_hours": 240.0, "amount": wage}]
                if extra_line:
                    source.append({"work_entry_type_id": late.id, "number_of_days": 9.0,
                                   "number_of_hours": 9.0, "amount": 0.0})
                with patch.object(provider, "_get_worked_day_lines_values", return_value=source), \
                        patch.object(cls, "_step_late_hours", return_value=hours):
                    lines = slip._get_worked_day_lines_values()
                attendance = [l for l in lines if l["work_entry_type_id"] == work.id]
                self.assertEqual(len(attendance), 1)
                self.assertAlmostEqual(attendance[0]["number_of_days"], exp_days)
                self.assertAlmostEqual(attendance[0]["amount"], wage / 30 * exp_days, places=2)
                late_lines = [l for l in lines if l["work_entry_type_id"] == late.id]
                self.assertEqual(len(late_lines), 1 if hours else int(extra_line))
                if hours:
                    self.assertAlmostEqual(late_lines[0]["number_of_hours"], hours)
                    self.assertEqual(late_lines[0]["amount"], 0.0)
        self.assertEqual(round(wage / 30 * 29.65), 547095)
