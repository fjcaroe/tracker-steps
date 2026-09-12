from odoo import Command
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon

from .test_management_costs import extra_analytic_account_vals


@tagged("post_install", "-at_install")
class TestFase2Variance(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.env.user.company_ids = [Command.link(cls.company.id)]
        cls.env.user.company_id = cls.company

        cls.plan = cls.env["account.analytic.plan"].create({"name": "MC Plan"})
        cls.aa = cls.env["account.analytic.account"].create(dict({
            "name": "AA Centro", "plan_id": cls.plan.id, "company_id": cls.company.id,
        }, **extra_analytic_account_vals(cls.env, cls.company)))
        cls.group = cls.env["step.management.budget.group"].create({
            "code": "MOA", "name": "Mano de obra", "company_id": cls.company.id,
            "flow_type": "cost",
        })
        cls.center = cls.env["step.management.cost.center"].create({
            "code": "C1", "name": "Centro 1", "company_id": cls.company.id,
            "hectares": 10.0, "analytic_account_id": cls.aa.id,
        })
        cls.product_a.categ_id.management_budget_group_id = cls.group.id

        cls.budget = cls.env["step.management.operational.budget"].create({
            "description": "Ppto prueba real", "company_id": cls.company.id,
            "season": "2026/2027", "currency_id": cls.company.currency_id.id,
            "allocation_ids": [Command.create({"center_id": cls.center.id, "hectares": 10.0})],
            "line_ids": [Command.create({
                "center_id": cls.center.id, "group_id": cls.group.id, "category": "labor",
                "indicator": "Poda", "hectares": 10.0, "quantity": 12.0, "unit_price": 1000.0,
                "month_ids": [Command.create({"month": "jun", "quantity": 12.0, "unit_price": 1000.0})],
            })],
        })

    def _bill(self, move_type, price, product=None, date="2026-06-15", post=True):
        product = product or self.product_a
        move = self.env["account.move"].create({
            "move_type": move_type,
            "partner_id": self.partner_a.id,
            "invoice_date": date,
            "date": date,
            "company_id": self.company.id,
            "invoice_line_ids": [Command.create({
                "product_id": product.id,
                "quantity": 1,
                "price_unit": price,
                "analytic_distribution": {str(self.aa.id): 100.0},
            })],
        })
        if post:
            move.action_post()
        return move

    def _wizard(self):
        return self.env["step.management.budget.variance.wizard"].create({
            "budget_id": self.budget.id,
            "date_from": "2026-05-01", "date_to": "2027-04-30",
        })

    def test_actual_from_posted_move_only(self):
        self._bill("in_invoice", 10000.0)          # publicada
        self._bill("in_invoice", 4000.0, post=False)  # borrador: NO cuenta
        wiz = self._wizard()
        wiz.action_compute()
        self.assertTrue(wiz.computed)
        line = wiz.line_ids.filtered(lambda l: l.flow_type == "cost")
        self.assertEqual(len(line), 1)
        self.assertAlmostEqual(line.budget_amount, 12000.0)
        self.assertAlmostEqual(line.actual_amount, 10000.0)
        self.assertAlmostEqual(line.variance, -2000.0)
        self.assertAlmostEqual(line.variance_percent, -2000.0 * 100 / 12000.0, places=2)
        self.assertGreaterEqual(line.move_count, 1)
        self.assertAlmostEqual(wiz.total_actual_cost, 10000.0)
        self.assertAlmostEqual(wiz.total_variance_cost, -2000.0)

    def test_credit_note_reverses_actual(self):
        self._bill("in_invoice", 10000.0)
        self._bill("in_refund", 3000.0)
        wiz = self._wizard()
        wiz.action_compute()
        line = wiz.line_ids.filtered(lambda l: l.flow_type == "cost")
        self.assertAlmostEqual(line.actual_amount, 7000.0)
        self.assertAlmostEqual(line.actual_qty, 0.0)

    def test_unclassified_bucket(self):
        # product_b sin grupo en su categoría
        self.product_b.categ_id.management_budget_group_id = False
        self.product_b.management_budget_group_id = False
        self._bill("in_invoice", 5000.0, product=self.product_b)
        wiz = self._wizard()
        wiz.action_compute()
        unclassified = wiz.line_ids.filtered(lambda l: not l.group_id and l.actual_amount)
        self.assertEqual(len(unclassified), 1)
        self.assertEqual(unclassified.group_label, "Sin clasificar")
        self.assertAlmostEqual(unclassified.actual_amount, 5000.0)

    def test_only_deviations_filter(self):
        self._bill("in_invoice", 12000.0)  # calza exacto con el presupuesto
        wiz = self._wizard()
        wiz.only_deviations = True
        wiz.action_compute()
        self.assertFalse(wiz.line_ids.filtered(
            lambda l: l.center_id == self.center and l.month == "jun" and l.flow_type == "cost"
        ))

    def test_out_of_range_date_excluded(self):
        self._bill("in_invoice", 9000.0, date="2025-06-15")  # temporada anterior
        wiz = self._wizard()
        wiz.action_compute()
        cost = wiz.line_ids.filtered(lambda l: l.flow_type == "cost")
        self.assertAlmostEqual(sum(cost.mapped("actual_amount")), 0.0)
