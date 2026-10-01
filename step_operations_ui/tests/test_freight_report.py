from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFreightReport(TransactionCase):
    """La tabla "real" (Studio, hoja Costeo) puede no existir en algunas
    bases (entonces la vista debe quedar vacía en lugar de romper la
    instalación) o puede ya existir con datos propios de esa base (p. ej.
    en Desarrollo, donde el cliente la usa activamente): por eso estas
    pruebas no asumen un conteo total fijo, solo que las vistas son
    consultables y que lo que crea esta misma prueba se refleja bien.
    """

    def test_cost_report_view_is_queryable(self):
        # No debe lanzar error sin importar si la tabla de Studio existe o no.
        self.assertGreaterEqual(self.env["step.freight.cost.report"].search_count([]), 0)

    def test_plan_vs_actual_reflects_planned_amount(self):
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
        # La vista lee la tabla real vía SQL crudo: hay que forzar el flush
        # de los cómputos pendientes (amount_total) antes de consultarla,
        # igual que ocurriría de forma natural entre dos pedidos XML-RPC/HTTP.
        self.env.flush_all()
        rows = self.env["step.freight.plan.vs.actual"].search([
            ("product_id", "=", freight_product.id),
        ])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.planned_amount, 20000)
        self.assertEqual(rows.diff_amount, rows.real_amount - 20000)
