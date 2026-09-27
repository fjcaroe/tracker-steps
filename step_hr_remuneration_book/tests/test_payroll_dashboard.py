from types import SimpleNamespace

from odoo.addons.step_hr_previred.tools import previred

from .common import RemunerationBookCommon


class TestPayrollDashboard(RemunerationBookCommon):

    def test_book_summary_uses_official_dt_codes(self):
        dataset = SimpleNamespace(lines=[object()], totals={
            "2101": 500000,
            "2311": 10000,
            "3188": 100000,
            "5201": 510000,
            "5501": 410000,
            # 5210 no debe reemplazar al Total Haberes 5201.
            "5210": 500000,
        })

        data = self.env["hr.payslip"]._steps_book_values(dataset)

        self.assertEqual(data["base_salary"], 500000)
        self.assertEqual(data["total_income"], 510000)
        self.assertEqual(data["net"], 410000)
        self.assertEqual(data["advances"], 100000)
        self.assertEqual(data["family_allowance"], 10000)
        self.assertEqual(
            self.env["hr.payslip"]._steps_percent(
                data["base_salary"], data["total_income"]),
            98.0,
        )

    def test_previred_summary_groups_ticket_20_fields(self):
        row = ["" for _index in range(previred.FIELD_COUNT)]
        expected_worker = 0
        expected_employer = 0
        for index, position in enumerate(
                (28, 70, 80, 81, 90, 85, 22, 30, 43, 101), start=1):
            row[position - 1] = str(index * 10)
            expected_worker += index * 10
        for index, position in enumerate(
                (29, 94, 95, 71, 98, 102), start=1):
            row[position - 1] = str(index * 100)
            expected_employer += index * 100
        record = SimpleNamespace(rows=[row])

        summary = self.env["hr.payslip"]._steps_summarize_previred_records(
            [record])

        self.assertEqual(summary["worker"], expected_worker)
        self.assertEqual(summary["employer"], expected_employer)
        self.assertEqual(summary["paid"], expected_worker + expected_employer)
        self.assertTrue(summary["available"])
