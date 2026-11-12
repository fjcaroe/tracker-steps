from datetime import datetime, timedelta

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestNursery(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.company = env.company
        cls.warehouse = env["stock.warehouse"].search([("company_id", "=", cls.company.id)], limit=1)
        cls.unit = env.ref("uom.product_uom_unit")
        cls.plant, cls.seed, cls.tray = env["product.product"].create([
            {"name": "QA Plantín", "is_storable": True, "tracking": "lot", "uom_id": cls.unit.id},
            {"name": "QA Semilla", "is_storable": True, "tracking": "lot", "uom_id": cls.unit.id},
            {"name": "QA Bandeja 128", "is_storable": True, "uom_id": cls.unit.id},
        ])
        cls.customer = env["res.partner"].create({"name": "QA Vivero"})
        cls.species = env["step.especie"].create({"name": "QA Especie de vivero"})
        cls.season = env["step.temporada"].create({"name": "QA Temporada de vivero"})
        cls.cycle = env["step.nursery.cycle"].create({
            "name": "QA Ciclo 35 días", "species_id": cls.species.id, "season_id": cls.season.id,
            "cycle_days": 35, "extra_pct": 10, "tray_id": cls.tray.id, "cells_per_tray": 128,
        })
        cls.bom = env["mrp.bom"].create({
            "product_tmpl_id": cls.plant.product_tmpl_id.id, "product_qty": 1,
            "bom_line_ids": [Command.create({"product_id": cls.seed.id, "product_qty": 1})],
        })
        cls.delivery = datetime(2027, 1, 19, 13)
        cls.location = env["stock.location"].create({
            "name": "QA Mesón", "location_id": cls.warehouse.lot_stock_id.id,
            "company_id": cls.company.id, "usage": "internal", "step_nursery_tray_capacity": 10,
        })

    def _plan(self, quantity=1000, delivery=None):
        order = self.env["sale.order"].create({
            "partner_id": self.customer.id, "warehouse_id": self.warehouse.id,
            "commitment_date": delivery or self.delivery,
            "order_line": [Command.create({"product_id": self.plant.id,
                                           "product_uom_qty": quantity, "price_unit": 100})],
        })
        return self.env["step.nursery.plan"].create({
            "sale_line_id": order.order_line.id, "promised_at": order.commitment_date,
            "cycle_id": self.cycle.id, "bom_id": self.bom.id,
        })

    def test_sowing_from_order_without_increasing_commitment(self):
        plan = self._plan()
        plan.sale_line_id.order_id.action_confirm()
        plan.action_create_production()
        native = plan.production_id
        self.assertEqual(plan.sowing_at, self.delivery - timedelta(days=35))
        self.assertEqual((plan.promised_units, plan.tray_count, plan.sowing_units), (1000, 9, 1152))
        self.assertEqual(native.product_qty, 1152)
        self.assertEqual(native.date_start, plan.sowing_at)
        self.assertEqual(plan.sale_line_id.product_uom_qty, 1000)
        self.assertEqual(plan.action_create_production()["res_id"], native.id)
        self.assertEqual(plan.sale_line_id.order_id.picking_ids.move_ids.product_uom_qty, 1000)

    def test_capacity_uses_daily_peak_and_inclusive_end(self):
        plans = self._plan() | self._plan(750) | self._plan(500)
        slots = self.env["step.nursery.slot"]
        for plan, start, end, trays in zip(plans, [0, 4, 7], [9, 6, 8], [5, 4, 7]):
            slots |= slots.create({
                "plan_id": plan.id, "location_id": self.location.id, "trays": trays,
                "start_date": self.delivery.date() + timedelta(days=start),
                "end_date": self.delivery.date() + timedelta(days=end),
            })
        self.assertEqual(slots.mapped("peak_trays"), [12, 9, 12])
        self.assertEqual(slots.mapped("over_capacity"), [True, False, True])

    def test_seed_sample_and_production_log(self):
        plan = self._plan()
        plan.sale_line_id.order_id.action_confirm()
        plan.action_create_production()
        seed_lot = self.env["stock.lot"].create({
            "name": "QA-SEM-01", "product_id": self.seed.id, "company_id": self.company.id,
            "step_nursery_seed": True, "step_nursery_sample": 50,
            "step_nursery_germinated": 41, "step_nursery_weight_g": 12.5,
        })
        self.assertEqual(seed_lot.step_nursery_germination_pct, 82)
        self.assertEqual(seed_lot.step_nursery_seeds_per_g, 4)
        event = self.env["step.nursery.event"].create({
            "production_id": plan.production_id.id, "kind": "germination",
            "sample_count": 40, "germinated_count": 33,
        })
        self.assertEqual(event.germination_pct, 82.5)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            event.germinated_count = 41

    def test_views_and_company_boundary(self):
        plan = self._plan()
        company = self.env["res.company"].create({"name": "QA Vivero separado"})
        user = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "QA Operador", "login": "nursery-isolation-qa",
            "company_id": company.id, "company_ids": [Command.set(company.ids)],
            "groups_id": [Command.set(self.env.ref("step_nursery_operations.group_nursery_operator").ids)],
        })
        foreign = plan.with_user(user).with_company(company)
        self.assertFalse(foreign.search([("id", "=", plan.id)]))
        with self.assertRaises(AccessError):
            foreign.action_create_production()
        for model in ("step.nursery.plan", "step.nursery.cycle", "stock.lot", "mrp.production"):
            self.assertTrue(self.env[model].get_view(view_type="form")["arch"])
        self.assertTrue(self.env.ref("step_nursery_operations.menu_nursery_plan").action)
