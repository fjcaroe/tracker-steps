from datetime import date

from odoo import Command
from odoo.tests import TransactionCase, tagged
from odoo.tools.safe_eval import safe_eval


@tagged("post_install", "-at_install")
class TestAllowanceDays(TransactionCase):
    def test_company_options_apply_to_each_native_rule(self):
        company = self.env["res.company"].create({"name": "T155 test company"})
        self.assertFalse(company.payroll_whole_days_meal)
        self.assertFalse(company.payroll_whole_days_transport)
        contract = self.env["hr.contract"].new({
            "company_id": company.id,
            "date_start": date(2026, 10, 1),
            "colocation": 35000,
            "movility": 25000,
        })
        slip = self.env["hr.payslip"].new({
            "company_id": company.id,
            "contract_id": contract,
            "date_from": date(2026, 10, 1),
            "date_to": date(2026, 10, 31),
            "worked_days_line_ids": [Command.create({
                "work_entry_type_id": self.env.ref("hr_work_entry.work_entry_type_attendance").id,
                "number_of_days": 29.01,
            })],
        })
        def compute(name):
            rule = self.env.ref("l10n_cl_simpledigital_payroll.hr_rule_" + name)
            values = {"payslip": slip, "contract": contract}
            safe_eval(rule.amount_python_compute, values, mode="exec", nocopy=True)
            return values["result"]

        regular_meal = compute("colocation")
        regular_transport = compute("movility")
        company.payroll_whole_days_meal = True
        self.assertEqual(compute("colocation"), 35000)
        self.assertEqual(compute("movility"), regular_transport)
        company.write({"payroll_whole_days_meal": False, "payroll_whole_days_transport": True})
        self.assertEqual(compute("colocation"), regular_meal)
        self.assertEqual(compute("movility"), 25000)
        company.payroll_whole_days_meal = True
        for days, expected in ((29.5, 30), (29, 29), (28.01, 29), (0, 0), (31, 30)):
            slip.worked_days_line_ids.number_of_days = days
            self.assertAlmostEqual(compute("colocation"), 35000 * expected / 30)
            self.assertAlmostEqual(compute("movility"), 25000 * expected / 30)
            self.assertEqual(slip.worked_days_line_ids.number_of_days, days)
