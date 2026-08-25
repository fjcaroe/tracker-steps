from datetime import datetime

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "step_colaciones")
class TestColaciones(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.expense_account = cls.env["account.account"].search([
            ("company_ids", "in", cls.company.id),
            ("account_type", "in", ("expense", "expense_direct_cost")),
            ("deprecated", "=", False),
        ], limit=1)
        cls.provision_account = cls.env["account.account"].search([
            ("company_ids", "in", cls.company.id),
            ("account_type", "=", "liability_current"),
            ("deprecated", "=", False),
        ], limit=1)
        cls.journal = cls.env["account.journal"].search([
            ("company_id", "=", cls.company.id),
            ("type", "=", "general"),
        ], limit=1)
        if not cls.expense_account or not cls.provision_account or not cls.journal:
            raise AssertionError("La base de pruebas debe tener un plan contable y diario general.")
        cls.journal.default_account_id = cls.provision_account
        cls.company.write({
            "colaciones_provision_journal_id": cls.journal.id,
            "colaciones_accounting_responsible_id": cls.env.user.id,
        })
        cls.product = cls.env["product.template"].create({
            "name": "Almuerzo estándar",
            "is_meal": True,
            "property_account_expense_id": cls.expense_account.id,
        })
        cls.supplier = cls.env["res.partner"].create({
            "name": "Casino de prueba",
            "supplier_rank": 1,
            "is_meal_supplier": True,
        })
        cls.employee = cls.env["hr.employee"].create({
            "name": "Trabajador Prueba",
            "company_id": cls.company.id,
            "meal_eligible": True,
            "barcode": "MEAL001",
            "pin": "4321",
            "meal_nfc_uid": "NFC-001",
        })
        cls.analytic_plan = cls.env["account.analytic.plan"].create({
            "name": "Plan colaciones prueba",
        })
        cls.analytic_account = cls.env["account.analytic.account"].create({
            "name": "Centro colaciones prueba",
            "plan_id": cls.analytic_plan.id,
            "company_id": cls.company.id,
        })
        cls.employee.write({
            "meal_distribution_mode": "fixed",
            "meal_analytic_distribution": {str(cls.analytic_account.id): 100.0},
        })
        cls.tariff = cls.env["step.colacion.tariff"].create({
            "name": "Tarifa prueba",
            "supplier_id": cls.supplier.id,
            "company_id": cls.company.id,
            "currency_id": cls.company.currency_id.id,
            "valid_from": "2026-01-01",
            "line_ids": [(0, 0, {
                "product_tmpl_id": cls.product.id,
                "price": 2500,
            })],
        })
        cls.tariff.action_activate()
        cls.totem = cls.env["step.colacion.totem"].create({
            "name": "Tótem prueba",
            "code": "TOTEM-TEST",
            "company_id": cls.company.id,
            "product_tmpl_id": cls.product.id,
            "supplier_id": cls.supplier.id,
            "identification_method": "barcode",
        })

    def test_totem_registration_is_idempotent(self):
        first = self.totem.register_identifier(
            "MEAL001", "uuid-test-1", event_datetime="2026-08-21T12:00:00Z", offline=False
        )
        repeated = self.totem.register_identifier(
            "MEAL001", "uuid-test-1", event_datetime="2026-08-21T12:00:00Z", offline=False
        )
        self.assertTrue(first["ok"])
        self.assertTrue(repeated["duplicate"])
        self.assertEqual(self.env["step.colacion.registration"].search_count([
            ("client_uuid", "=", "uuid-test-1")
        ]), 1)

    def test_totem_url_opens_standalone_app(self):
        # Sin URL propia configurada se conserva la ruta historica del dominio.
        self.company.colaciones_pwa_base_url = False
        self.totem.invalidate_recordset(["totem_url"])
        self.assertIn("/colaciones/app/#token=", self.totem.totem_url)
        self.assertTrue(self.totem.totem_url.endswith(self.totem.access_token))

    def test_one_product_per_employee_day(self):
        values = {
            "event_datetime": datetime(2026, 8, 20, 12, 0, 0),
            "employee_id": self.employee.id,
            "product_tmpl_id": self.product.id,
            "supplier_id": self.supplier.id,
            "company_id": self.company.id,
        }
        self.env["step.colacion.registration"].create(values)
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self.env["step.colacion.registration"].create(values)

    def test_validation_snapshots_current_rate(self):
        registration = self.env["step.colacion.registration"].create({
            "event_datetime": datetime(2026, 8, 19, 12, 0, 0),
            "employee_id": self.employee.id,
            "product_tmpl_id": self.product.id,
            "supplier_id": self.supplier.id,
            "company_id": self.company.id,
        })
        registration.action_validate()
        self.assertEqual(registration.state, "validated")
        self.assertEqual(registration.unit_cost, 2500)
        self.assertEqual(registration.total_cost, 2500)

    def test_validation_requires_rate(self):
        other_product = self.env["product.template"].create({"name": "Cena", "is_meal": True})
        registration = self.env["step.colacion.registration"].create({
            "event_datetime": datetime(2026, 8, 18, 12, 0, 0),
            "employee_id": self.employee.id,
            "product_tmpl_id": other_product.id,
            "supplier_id": self.supplier.id,
            "company_id": self.company.id,
        })
        with self.assertRaises(UserError):
            registration.action_validate()

    def test_costing_snapshots_accounts_and_fixed_distribution(self):
        registration = self.env["step.colacion.registration"].create({
            "event_datetime": datetime(2026, 8, 17, 12, 0, 0),
            "employee_id": self.employee.id,
            "product_tmpl_id": self.product.id,
            "supplier_id": self.supplier.id,
            "company_id": self.company.id,
        })
        registration.action_validate()
        registration.action_cost()
        self.assertEqual(registration.state, "costed")
        self.assertEqual(registration.expense_account_id, self.expense_account)
        self.assertEqual(registration.provision_account_id, self.provision_account)
        self.assertEqual(registration.provision_journal_id, self.journal)
        self.assertEqual(registration.analytic_source, "fixed")
        self.assertEqual(registration.analytic_distribution, {str(self.analytic_account.id): 100.0})

    def test_dynamic_without_hours_falls_back_and_marks_warning(self):
        self.employee.meal_distribution_mode = "dynamic"
        registration = self.env["step.colacion.registration"].create({
            "event_datetime": datetime(2026, 8, 16, 12, 0, 0),
            "employee_id": self.employee.id,
            "product_tmpl_id": self.product.id,
            "supplier_id": self.supplier.id,
            "company_id": self.company.id,
        })
        registration.action_validate()
        registration.action_cost()
        self.assertEqual(registration.state, "costed")
        self.assertEqual(registration.analytic_source, "fixed_fallback")
        self.assertTrue(registration.analytic_fallback_used)
        self.assertTrue(registration.analytic_warning)

    def test_accounting_creates_balanced_move_and_is_idempotent(self):
        registration = self.env["step.colacion.registration"].create({
            "event_datetime": datetime(2026, 8, 15, 12, 0, 0),
            "employee_id": self.employee.id,
            "product_tmpl_id": self.product.id,
            "supplier_id": self.supplier.id,
            "company_id": self.company.id,
        })
        registration.action_validate()
        registration.action_cost()
        registration.action_account()
        self.assertEqual(registration.state, "accounted")
        self.assertTrue(registration.account_move_id)
        self.assertEqual(registration.account_move_id.state, "draft")
        self.assertEqual(
            sum(registration.account_move_id.line_ids.mapped("debit")),
            sum(registration.account_move_id.line_ids.mapped("credit")),
        )
        self.assertEqual(
            registration.account_move_id.line_ids.filtered(
                lambda line: line.account_id == self.expense_account
            ).analytic_distribution,
            {str(self.analytic_account.id): 100.0},
        )
        with self.assertRaises(UserError):
            registration.action_account()
