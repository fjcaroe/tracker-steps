from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestBpaInventoryBridge(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.product = cls.env["product.product"].create({"name": "Fungicida prueba", "type": "consu"})

    def _application(self, state="status3"):
        return self.env["x_aplicacion_foliar"].create({
            "x_name": "BPA prueba inventario",
            "x_studio_nmero_ot_bpa": "OT-BPA-1",
            "state": state,
            "company_id": self.company.id,
        })

    def test_generate_inventory_move_creates_picking_with_lines(self):
        application = self._application()
        self.env["step.bpa.inventory.consumption.line"].create({
            "application_id": application.id, "product_id": self.product.id, "product_qty": 5.0,
        })
        application.action_generate_inventory_move()
        self.assertTrue(application.inventory_picking_id)
        picking = application.inventory_picking_id
        self.assertEqual(picking.origin, "OT-BPA-1")
        self.assertEqual(len(picking.move_ids), 1)
        move = picking.move_ids[0]
        self.assertEqual(move.product_id, self.product)
        self.assertEqual(move.product_uom_qty, 5.0)
        self.assertEqual(move.location_id.name, "BPA/Stock")
        self.assertEqual(application.consumption_line_ids.inventory_move_id, move)

    def test_generate_inventory_move_is_idempotent(self):
        application = self._application()
        self.env["step.bpa.inventory.consumption.line"].create({
            "application_id": application.id, "product_id": self.product.id, "product_qty": 2.0,
        })
        application.action_generate_inventory_move()
        first_picking = application.inventory_picking_id
        application.action_generate_inventory_move()
        self.assertEqual(application.inventory_picking_id, first_picking)
        self.assertEqual(
            self.env["stock.picking"].search_count([("origin", "=", "OT-BPA-1")]), 1,
        )

    def test_generate_inventory_move_requires_costed_state(self):
        application = self._application(state="status1")
        self.env["step.bpa.inventory.consumption.line"].create({
            "application_id": application.id, "product_id": self.product.id, "product_qty": 1.0,
        })
        with self.assertRaises(UserError):
            application.action_generate_inventory_move()

    def test_generate_inventory_move_requires_consumption_lines(self):
        application = self._application()
        with self.assertRaises(UserError):
            application.action_generate_inventory_move()

    def test_generate_inventory_move_distributes_cost_by_hectare(self):
        """Ticket 23, punto 6: reparto por hectáreas, no en partes iguales."""
        analytic_plan = self.env["account.analytic.plan"].create({"name": "Plan cuarteles prueba"})
        account_a = self.env["account.analytic.account"].create({
            "name": "Cuartel A", "plan_id": analytic_plan.id,
        })
        account_b = self.env["account.analytic.account"].create({
            "name": "Cuartel B", "plan_id": analytic_plan.id,
        })
        application = self._application()
        self.env["step.bpa.inventory.consumption.line"].create({
            "application_id": application.id, "product_id": self.product.id, "product_qty": 10.0,
        })
        self.env["x_aplicacion_foliar_line_2f222"].create([
            {
                "x_name": "Maquinada cuartel A",
                "x_aplicacion_foliar_id": application.id,
                "x_studio_centro_costo": account_a.id,
                "x_studio_has_aplicadas": 3.0,
            },
            {
                "x_name": "Maquinada cuartel B",
                "x_aplicacion_foliar_id": application.id,
                "x_studio_centro_costo": account_b.id,
                "x_studio_has_aplicadas": 1.0,
            },
        ])
        application.action_generate_inventory_move()
        move = application.inventory_picking_id.move_ids
        self.assertEqual(
            move.analytic_distribution,
            {str(account_a.id): 75.0, str(account_b.id): 25.0},
        )

    def test_generate_inventory_move_without_cuarteles_has_no_distribution(self):
        application = self._application()
        self.env["step.bpa.inventory.consumption.line"].create({
            "application_id": application.id, "product_id": self.product.id, "product_qty": 1.0,
        })
        application.action_generate_inventory_move()
        move = application.inventory_picking_id.move_ids
        self.assertFalse(move.analytic_distribution)
