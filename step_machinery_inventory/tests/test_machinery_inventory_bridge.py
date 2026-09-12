from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMachineryInventoryBridge(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.product = cls.env["product.template"].create({
            "name": "Petróleo diésel prueba", "standard_price": 100, "type": "consu",
        })
        vehicle_model = cls.env["fleet.vehicle.model"].search([], limit=1)
        if not vehicle_model:
            brand = cls.env["fleet.vehicle.model.brand"].create({"name": "Prueba Maquinaria Inventario"})
            vehicle_model = cls.env["fleet.vehicle.model"].create({
                "name": "Tractor de prueba inventario", "brand_id": brand.id,
            })
        cls.vehicle = cls.env["fleet.vehicle"].create({
            "model_id": vehicle_model.id,
            "license_plate": "TEST-MQ-INV",
            "es_maquina": True,
            "step_product_id": cls.product.id,
            "step_total_hrs_mes": 100,
        })

    def _costed_usage(self, liters=3.0):
        usage = self.env["step.hrs.machinery"].create({
            "date": "2026-08-15", "folio": "TEST-MQ-INV", "company_id": self.company.id, "state": "done",
        })
        self.env["step.hrs.machinery.line"].create({
            "machinery_id": usage.id, "machinery_ids": self.vehicle.id,
            "hrs_maquina": 2.0, "lrts_combustible": liters,
        })
        usage.action_cost()
        return usage

    def test_generate_inventory_move_creates_picking_with_fuel_move(self):
        usage = self._costed_usage(liters=3.0)
        usage.action_generate_inventory_move()
        self.assertTrue(usage.inventory_picking_id)
        picking = usage.inventory_picking_id
        self.assertEqual(picking.origin, usage.name)
        self.assertEqual(len(picking.move_ids), 1)
        move = picking.move_ids[0]
        self.assertEqual(move.product_id, self.product.product_variant_id)
        self.assertEqual(move.product_uom_qty, 3.0)
        self.assertEqual(move.step_hrs_machinery_line_id, usage.hrs_machinery_line[0])
        self.assertEqual(move.location_id.name, "MQ/Stock")

    def test_generate_inventory_move_is_idempotent(self):
        usage = self._costed_usage()
        usage.action_generate_inventory_move()
        first_picking = usage.inventory_picking_id
        usage.action_generate_inventory_move()
        self.assertEqual(usage.inventory_picking_id, first_picking)
        self.assertEqual(
            self.env["stock.picking"].search_count([("origin", "=", usage.name)]), 1,
        )

    def test_generate_inventory_move_requires_costed_state(self):
        usage = self.env["step.hrs.machinery"].create({
            "date": "2026-08-15", "folio": "TEST-MQ-INV-DRAFT", "company_id": self.company.id,
        })
        self.env["step.hrs.machinery.line"].create({
            "machinery_id": usage.id, "machinery_ids": self.vehicle.id,
            "hrs_maquina": 2.0, "lrts_combustible": 1.0,
        })
        with self.assertRaises(UserError):
            usage.action_generate_inventory_move()

    def test_generate_inventory_move_requires_fuel_lines(self):
        usage = self.env["step.hrs.machinery"].create({
            "date": "2026-08-15", "folio": "TEST-MQ-INV-NOFUEL", "company_id": self.company.id, "state": "done",
        })
        self.env["step.hrs.machinery.line"].create({
            "machinery_id": usage.id, "machinery_ids": self.vehicle.id,
            "hrs_maquina": 2.0, "lrts_combustible": 0.0,
        })
        usage.action_cost()
        with self.assertRaises(UserError):
            usage.action_generate_inventory_move()

    def test_generate_inventory_move_stops_on_machine_missing_fuel_product(self):
        # Ticket 24, alternativa aprobada por el cliente en el punto 5: si una
        # máquina de la OT no tiene producto de combustible configurado,
        # Odoo debe detener el proceso y avisar cuál falta, no omitirla.
        vehicle_model = self.vehicle.model_id
        unconfigured_vehicle = self.env["fleet.vehicle"].create({
            "model_id": vehicle_model.id,
            "license_plate": "TEST-MQ-INV-SINPROD",
            "es_maquina": True,
            "step_total_hrs_mes": 100,
        })
        usage = self.env["step.hrs.machinery"].create({
            "date": "2026-08-15", "folio": "TEST-MQ-INV-MIXED", "company_id": self.company.id, "state": "done",
        })
        self.env["step.hrs.machinery.line"].create({
            "machinery_id": usage.id, "machinery_ids": self.vehicle.id,
            "hrs_maquina": 2.0, "lrts_combustible": 3.0,
        })
        self.env["step.hrs.machinery.line"].create({
            "machinery_id": usage.id, "machinery_ids": unconfigured_vehicle.id,
            "hrs_maquina": 1.0, "lrts_combustible": 2.0,
        })
        usage.action_cost()
        with self.assertRaises(UserError):
            usage.action_generate_inventory_move()
        self.assertFalse(usage.inventory_picking_id)
