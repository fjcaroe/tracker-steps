from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFreightPlan(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.freight_product = cls.env["product.template"].create({
            "name": "Flete transporte fruta",
            "is_flete": True,
        })
        cls.non_freight_product = cls.env["product.template"].create({
            "name": "Caja de embalaje",
            "is_flete": False,
        })

    def test_line_total_is_quantity_times_price(self):
        plan = self.env["x_planificacion_de_flete"].create({
            "x_name": "Planificación semana 1",
            "line_ids": [(0, 0, {
                "product_id": self.freight_product.id,
                "quantity": 4,
                "price": 15000,
            })],
        })
        self.assertEqual(plan.line_ids.amount_total, 60000)

    def test_plan_total_sums_all_lines(self):
        plan = self.env["x_planificacion_de_flete"].create({
            "x_name": "Planificación semana 2",
            "line_ids": [
                (0, 0, {"product_id": self.freight_product.id, "quantity": 2, "price": 10000}),
                (0, 0, {"product_id": self.freight_product.id, "quantity": 3, "price": 5000}),
            ],
        })
        self.assertEqual(plan.amount_total, 20000 + 15000)

    def test_line_rejects_product_not_marked_as_flete(self):
        plan = self.env["x_planificacion_de_flete"].create({"x_name": "Planificación semana 3"})
        with self.assertRaises(ValidationError):
            self.env["x_planificacion_de_flete_linea"].create({
                "plan_id": plan.id,
                "product_id": self.non_freight_product.id,
                "quantity": 1,
                "price": 1000,
            })

    def test_plan_total_updates_when_line_removed(self):
        plan = self.env["x_planificacion_de_flete"].create({
            "x_name": "Planificación semana 4",
            "line_ids": [(0, 0, {
                "product_id": self.freight_product.id,
                "quantity": 1,
                "price": 8000,
            })],
        })
        self.assertEqual(plan.amount_total, 8000)
        plan.line_ids.unlink()
        self.assertEqual(plan.amount_total, 0)

    def test_date_from_after_date_to_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.env["x_planificacion_de_flete"].create({
                "x_name": "Planificación con rango invertido",
                "date_from": "2026-10-10",
                "date_to": "2026-10-05",
            })

    def test_validate_requires_lines(self):
        plan = self.env["x_planificacion_de_flete"].create({"x_name": "Planificación sin líneas"})
        with self.assertRaises(ValidationError):
            plan.action_validate()

    def test_validate_and_reset_to_draft(self):
        plan = self.env["x_planificacion_de_flete"].create({
            "x_name": "Planificación a validar",
            "line_ids": [(0, 0, {
                "product_id": self.freight_product.id,
                "quantity": 1,
                "price": 5000,
            })],
        })
        plan.action_validate()
        self.assertEqual(plan.state, "validated")
        plan.action_reset_to_draft()
        self.assertEqual(plan.state, "draft")

    def test_line_currency_defaults_to_company_currency(self):
        plan = self.env["x_planificacion_de_flete"].create({
            "x_name": "Planificación moneda",
            "line_ids": [(0, 0, {
                "product_id": self.freight_product.id,
                "quantity": 1,
                "price": 1000,
            })],
        })
        self.assertEqual(plan.line_ids.currency_id, self.env.company.currency_id)

    def test_total_converts_foreign_currency_lines(self):
        foreign_currency = self.env["res.currency"].create({
            "name": "FLT",
            "symbol": "FLT",
        })
        self.env["res.currency.rate"].create({
            "currency_id": foreign_currency.id,
            "name": "2026-10-01",
            "rate": 2.0,  # 1 moneda base = 2 FLT -> 10 FLT = 5 moneda base
        })
        plan = self.env["x_planificacion_de_flete"].create({
            "x_name": "Planificación multimoneda",
            "x_studio_fecha": "2026-10-01",
            "line_ids": [(0, 0, {
                "product_id": self.freight_product.id,
                "quantity": 1,
                "price": 10,
                "currency_id": foreign_currency.id,
            })],
        })
        self.assertEqual(plan.amount_total, 5)
