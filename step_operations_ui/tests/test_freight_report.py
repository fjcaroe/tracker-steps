from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFreightReport(TransactionCase):
    """La tabla real (Studio) no existe en la base de pruebas: las vistas
    deben seguir funcionando (vacías) en vez de romper la carga del módulo.
    """

    def test_cost_report_view_is_queryable(self):
        self.assertEqual(self.env["step.freight.cost.report"].search_count([]), 0)

    def test_plan_vs_actual_reflects_planned_without_real_table(self):
        freight_product = self.env["product.template"].create({
            "name": "Flete transporte fruta (reporte)",
            "is_flete": True,
        })
        self.env["x_planificacion_de_flete"].create({
            "x_name": "Planificación reporte",
            "x_studio_fecha": "2026-10-05",
            "line_ids": [(0, 0, {
                "product_id": freight_product.id,
                "quantity": 2,
                "price": 10000,
            })],
        })
        rows = self.env["step.freight.plan.vs.actual"].search([
            ("product_id", "=", freight_product.id),
        ])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.planned_amount, 20000)
        self.assertEqual(rows.real_amount, 0)
        self.assertEqual(rows.diff_amount, -20000)
