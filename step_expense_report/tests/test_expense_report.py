from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestStepExpenseReport(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env["hr.employee"].create({"name": "Trabajador Prueba"})
        cls.product = cls.env["product.product"].create(
            {"name": "Combustible prueba", "can_be_expensed": True, "type": "service"}
        )

    def _sheet(self):
        expense = self.env["hr.expense"].create({
            "name": "Bencina", "employee_id": self.employee.id, "product_id": self.product.id,
            "total_amount_currency": 50000, "step_doc_type": "boleta", "step_doc_number": "1234",
        })
        sheet = self.env["hr.expense.sheet"].create(
            {"name": "Viaje", "employee_id": self.employee.id, "expense_line_ids": [(6, 0, expense.ids)]}
        )
        return sheet, expense

    def test_folio_sequence(self):
        s1, _e1 = self._sheet()
        s2, _e2 = self._sheet()
        self.assertRegex(s1.folio, r"^FC-\d{6}$")
        self.assertEqual(int(s2.folio[3:]), int(s1.folio[3:]) + 1)
        found = self.env["hr.expense.sheet"].search([("display_name", "ilike", s1.folio)])
        self.assertIn(s1, found)

    def test_doc_fields_saved(self):
        _s, e = self._sheet()
        self.assertEqual((e.step_doc_type, e.step_doc_number), ("boleta", "1234"))

    def test_vehicle_computations(self):
        s, _e = self._sheet()
        line = self.env["step.expense.vehicle.line"].create(
            {"sheet_id": s.id, "route": "Fundo - Ciudad", "start_reading": 1000, "end_reading": 1150, "liters": 15}
        )
        self.assertEqual(line.distance, 150)
        self.assertAlmostEqual(line.yield_km_l, 10.0)

    def test_vehicle_visibility_modes(self):
        s, _e = self._sheet()
        company = s.company_id
        company.step_expense_vehicle_mode = "optional"
        s.invalidate_recordset()
        self.assertFalse(s.show_vehicle)
        s.use_vehicle = True
        self.assertTrue(s.show_vehicle)
        company.step_expense_vehicle_mode = "never"
        s.invalidate_recordset()
        self.assertFalse(s.show_vehicle)
        company.step_expense_vehicle_mode = "always"
        s.invalidate_recordset()
        self.assertTrue(s.show_vehicle)

    def test_report_renders(self):
        s, _e = self._sheet()
        html, _fmt = self.env["ir.actions.report"]._render_qweb_html(
            "step_expense_report.report_expense_sheet_step", s.ids
        )
        text = html.decode()
        self.assertIn("RENDICIÓN DE GASTOS", text)
        self.assertIn(s.folio, text)
        self.assertIn("1234", text)
