from datetime import datetime, timedelta
from uuid import uuid4

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
        cls.species = env["step.especie"].create({"name": "QA Especie de vivero", "type_especie": "frutal", "group_especie": "baya"})
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

    def test_sales_schedule_uses_four_native_pickings(self):
        plan = self._plan(quantity=100000)
        line = plan.sale_line_id
        for day in range(4):
            self.env["step.nursery.delivery"].create({
                "line_id": line.id, "quantity": 25000, "delivery_at": self.delivery + timedelta(weeks=day),
            })
        line.order_id.action_confirm()
        moves = line.move_ids.filtered(lambda m: m.location_dest_id.usage == "customer")
        self.assertEqual(len(moves.picking_id), 4)
        self.assertEqual(moves.picking_id, line.order_id.picking_ids)
        self.assertEqual(sorted(moves.mapped("date_deadline")),
                         [self.delivery + timedelta(weeks=day) for day in range(4)])
        self.assertEqual(sum(moves.mapped("product_uom_qty")), 100000)

    def test_partial_return_reduces_tray_loan_from_native_moves(self):
        custody = self.env["stock.location"].create({
            "name": "QA Custodia fuera del origen", "company_id": self.company.id,
            "location_id": self.warehouse.view_location_id.id, "usage": "internal",
        })
        self.env["stock.quant"]._update_available_quantity(self.tray, self.warehouse.lot_stock_id, 10)
        loan = self.env["step.nursery.tray.loan"].create({
            "partner_id": self.customer.id, "product_id": self.tray.id, "quantity": 10,
            "due_date": self.delivery.date(), "transfer_type_id": self.warehouse.int_type_id.id,
            "origin_id": self.warehouse.lot_stock_id.id, "custody_id": custody.id,
        })
        loan.action_create_dispatch()
        picking = loan.dispatch_id
        picking.action_assign()
        picking.move_ids.picked = True
        picking.button_validate()
        self.assertEqual((loan.quantity_out, loan.quantity_pending), (10, 10))
        self.assertEqual(loan.action_create_dispatch()["res_id"], picking.id)
        form = loan.action_return_trays()
        wizard = self.env["stock.return.picking"].with_context(**form["context"]).create({})
        wizard.product_return_moves.quantity = 3
        returned = self.env["stock.picking"].browse(wizard.action_create_returns()["res_id"])
        returned.action_assign()
        returned.move_ids.picked = True
        returned.button_validate()
        self.assertEqual((loan.quantity_returned, loan.quantity_pending), (3, 7))

    def test_offline_events_replay_without_duplicate(self):
        plan = self._plan()
        plan.sale_line_id.order_id.action_confirm()
        plan.action_create_production()
        payload = {"id": str(uuid4()), "order_id": plan.production_id.id,
                   "performed_at": "2026-11-12 15:40:00", "kind": "germination",
                   "sample": 80, "germinated": 70}
        model = self.env["step.nursery.event"]
        first = model._ingest_offline_event(payload)
        self.assertEqual(model._ingest_offline_event(payload), first)
        self.assertEqual(first.germination_pct, 87.5)
        self.assertEqual(model.search_count([("offline_key", "=", payload["id"])]), 1)
        with self.assertRaises(ValidationError):
            model._ingest_offline_event(dict(payload, germinated=71))
        with self.assertRaises(ValidationError):
            model._ingest_offline_event(dict(payload, order_id=0))

    def test_batch_cost_absorbs_normal_waste_after_native_production(self):
        plan = self._plan(quantity=100)
        plan.sale_line_id.order_id.action_confirm()
        plan.action_create_production()
        native = plan.production_id
        self.seed.standard_price = 2
        seed_lot = self.env["stock.lot"].create({
            "name": "QA-SEM-COST", "product_id": self.seed.id, "company_id": self.company.id,
        })
        finished_lot = self.env["stock.lot"].create({
            "name": "QA-PLT-COST", "product_id": self.plant.id, "company_id": self.company.id,
        })
        self.env["stock.quant"]._update_available_quantity(
            self.seed, native.location_src_id, plan.sowing_units, lot_id=seed_lot)
        native.action_confirm()
        native.action_assign()
        native.lot_producing_id = finished_lot
        native.qty_producing = plan.sowing_units
        native.move_raw_ids.picked = True
        native.button_mark_done()
        self.assertEqual(native.state, "done")
        scrap = self.env["stock.scrap"].create({
            "product_id": self.plant.id, "product_uom_id": self.unit.id, "lot_id": finished_lot.id,
            "scrap_qty": 8, "location_id": native.location_dest_id.id,
            "company_id": self.company.id, "step_nursery_waste_kind": "normal",
        })
        scrap.action_validate()
        report = self.env["step.nursery.batch.cost.report"].browse(native.action_step_nursery_batch_cost()["res_id"])
        self.assertEqual((report.produced, report.normal_waste, report.useful), (128, 8, 120))
        self.assertAlmostEqual(report.unit_cost, 256 / 120, places=4)
        self.assertEqual(report.balance_cost, 256)

    def test_maquila_reserves_only_requested_owner_and_lot(self):
        plan = self._plan(quantity=100)
        plan.sale_line_id.order_id.action_confirm()
        plan.action_create_production()
        native = plan.production_id
        owner2 = self.env["res.partner"].create({"name": "QA Segundo cliente de semilla"})
        custody_location = self.env["stock.location"].create({
            "name": "QA Semilla ajena", "company_id": self.company.id,
            "location_id": self.warehouse.view_location_id.id, "usage": "internal",
        })
        seed_lot = self.env["stock.lot"].create({
            "name": "QA-SEM-CUST", "product_id": self.seed.id, "company_id": self.company.id,
        })
        receipt = self.env["stock.picking"].create({
            "partner_id": self.customer.id, "picking_type_id": self.warehouse.in_type_id.id,
            "location_id": self.env.ref("stock.stock_location_suppliers").id,
            "location_dest_id": custody_location.id,
            "move_ids": [Command.create({
                "name": self.seed.name, "product_id": self.seed.id, "product_uom_qty": 60,
                "product_uom": self.unit.id,
            })],
        })
        receipt.action_confirm()
        receipt.move_line_ids.unlink()
        received = self.env["stock.move.line"].create({
            "move_id": receipt.move_ids.id, "picking_id": receipt.id, "product_id": self.seed.id,
            "product_uom_id": self.unit.id, "quantity": 60, "lot_id": seed_lot.id, "owner_id": self.customer.id,
            "location_id": receipt.location_id.id, "location_dest_id": custody_location.id,
            "company_id": self.company.id, "picked": True,
        })
        receipt.button_validate()
        custody = self.env["step.nursery.custody"].create({"receipt_line_id": received.id})
        self.env["stock.quant"]._update_available_quantity(
            self.seed, custody_location, 200, lot_id=seed_lot, owner_id=owner2)
        native.step_nursery_custody_id = custody
        native.action_confirm()
        native.action_assign()
        self.assertEqual(native.move_raw_ids.location_id, custody_location)
        self.assertEqual(native.move_raw_ids.move_line_ids.owner_id, self.customer)
        self.assertEqual(native.move_raw_ids.move_line_ids.lot_id, seed_lot)
        self.assertEqual(native.move_raw_ids.quantity, 60)
        self.assertEqual(custody.available, 60)
        self.assertFalse(receipt.move_ids.stock_valuation_layer_ids)
        self.env["stock.quant"]._update_available_quantity(
            self.seed, custody_location, 68, lot_id=seed_lot, owner_id=self.customer)
        native.action_assign()
        self.assertEqual(native.move_raw_ids.quantity, 128)
        native.lot_producing_id = self.env["stock.lot"].create({
            "name": "QA-PLT-CUST", "product_id": self.plant.id, "company_id": self.company.id,
        })
        native.qty_producing = 128
        native.move_raw_ids.picked = True
        native.button_mark_done()
        self.assertEqual(native.state, "done")
        self.assertEqual(native.move_raw_ids.move_line_ids.owner_id, self.customer)
        self.assertEqual(native.move_raw_ids.move_line_ids.lot_id, seed_lot)
        self.assertEqual(custody.consumed, 128)
        self.assertEqual(custody.available, 0)
        self.assertFalse(native.move_raw_ids.stock_valuation_layer_ids)
        package = self.env["stock.quant.package"].create({"step_nursery_production_id": native.id})
        self.assertEqual(package.step_nursery_package_customer_id, self.customer)
        package.action_step_nursery_mark_sown()
        self.assertTrue(package.step_nursery_sown_at)
        html, _ = self.env["ir.actions.report"]._render_qweb_html(
            "step_nursery_operations.action_nursery_package_label", package.ids)
        self.assertIn(b"QA-PLT-CUST", html)
        self.assertIn(b"MAQUILA", html)
        service = self.env["product.product"].create({"name": "QA Servicio de siembra", "type": "service"})
        bill = self.env["step.nursery.service.bill"].create({
            "production_id": native.id, "basis": "trays", "service_id": service.id, "price": 1000,
        })
        bill.action_create_invoice()
        self.assertEqual(bill.invoice_id.state, "draft")
        self.assertEqual(bill.invoice_id.partner_id, self.customer)
        self.assertEqual(bill.invoice_id.invoice_line_ids.quantity, 1)
        self.assertEqual(bill.action_create_invoice()["res_id"], bill.invoice_id.id)

    def test_combined_dispatch_uses_actual_plant_and_tray_movements(self):
        plan = self._plan(quantity=25)
        plan.sale_line_id.order_id.action_confirm()
        picking = plan.sale_line_id.order_id.picking_ids
        lot = self.env["stock.lot"].create({
            "name": "QA-SAL-LOT", "product_id": self.plant.id, "company_id": self.company.id,
        })
        self.env["stock.quant"]._update_available_quantity(self.plant, picking.location_id, 25, lot_id=lot)
        picking.action_assign()
        picking.move_ids.picked = True
        picking.button_validate()
        custody = self.env["stock.location"].create({
            "name": "QA Bandejas en cliente", "company_id": self.company.id,
            "location_id": self.warehouse.view_location_id.id, "usage": "internal",
        })
        self.env["stock.quant"]._update_available_quantity(self.tray, self.warehouse.lot_stock_id, 2)
        loan = self.env["step.nursery.tray.loan"].create({
            "partner_id": self.customer.id, "product_id": self.tray.id, "quantity": 2,
            "due_date": self.delivery.date(), "transfer_type_id": self.warehouse.int_type_id.id,
            "origin_id": self.warehouse.lot_stock_id.id, "custody_id": custody.id, "shipment_id": picking.id,
        })
        loan.action_create_dispatch()
        loan.dispatch_id.action_assign()
        loan.dispatch_id.move_ids.picked = True
        loan.dispatch_id.button_validate()
        action = picking.action_step_nursery_dispatch_summary()
        self.assertEqual(action["report_name"], "step_nursery_operations.nursery_dispatch_summary")
        html, _ = self.env["ir.actions.report"]._render_qweb_html(
            "step_nursery_operations.action_nursery_dispatch_summary", picking.ids)
        self.assertIn(b"QA-SAL-LOT", html)
        self.assertIn(b"QA Bandeja 128", html)

    def test_overdue_loan_creates_one_draft_for_remaining_quantity(self):
        custody = self.env["stock.location"].create({
            "name": "QA Vencidos en cliente", "company_id": self.company.id,
            "location_id": self.warehouse.view_location_id.id, "usage": "internal",
        })
        if not self.env["account.journal"].search_count([
            ("company_id", "=", self.company.id), ("type", "=", "sale"),
        ]):
            self.env["account.journal"].create({
                "name": "QA Diario de ventas", "code": "QASAL", "type": "sale", "company_id": self.company.id,
            })
        income = self.env["account.account"].create({
            "name": "QA Recuperación de bandejas", "code": "98765123", "account_type": "income",
            "company_ids": [Command.set(self.company.ids)],
        })
        charge = self.env["product.product"].create({
            "name": "QA Cargo por bandeja", "type": "service", "property_account_income_id": income.id,
        })
        self.env["stock.quant"]._update_available_quantity(self.tray, self.warehouse.lot_stock_id, 3)
        loan = self.env["step.nursery.tray.loan"].create({
            "partner_id": self.customer.id, "product_id": self.tray.id, "quantity": 3,
            "due_date": "2020-01-01", "transfer_type_id": self.warehouse.int_type_id.id,
            "origin_id": self.warehouse.lot_stock_id.id, "custody_id": custody.id,
            "charge_product_id": charge.id, "charge_price": 20,
        })
        loan.action_create_dispatch()
        loan.dispatch_id.action_assign()
        loan.dispatch_id.move_ids.picked = True
        loan.dispatch_id.button_validate()
        action = loan.action_draft_charge()
        self.assertEqual(action["res_id"], loan.invoice_id.id)
        self.assertEqual(loan.action_draft_charge()["res_id"], action["res_id"])
        self.assertEqual(loan.invoice_id.state, "draft")
        self.assertEqual(loan.invoice_id.invoice_line_ids.quantity, 3)
        self.assertEqual(loan.invoice_id.invoice_line_ids.price_unit, 20)

    def test_seed_weight_converts_at_lot_rate_without_overstating_units(self):
        lot = self.env["stock.lot"].create({
            "name": "QA-SEM-PESO", "product_id": self.seed.id, "company_id": self.company.id,
            "step_nursery_seed": True, "step_nursery_sample": 50, "step_nursery_weight_g": 12.5,
        })
        receipt = self.env["stock.picking"].create({
            "partner_id": self.customer.id, "picking_type_id": self.warehouse.in_type_id.id,
            "location_id": self.env.ref("stock.stock_location_suppliers").id,
            "location_dest_id": self.warehouse.lot_stock_id.id,
            "move_ids": [Command.create({
                "name": self.seed.name, "product_id": self.seed.id, "product_uom_qty": 40,
                "product_uom": self.unit.id,
            })],
        })
        receipt.action_confirm()
        receipt.move_line_ids.unlink()
        line = self.env["stock.move.line"].create({
            "move_id": receipt.move_ids.id, "picking_id": receipt.id, "product_id": self.seed.id,
            "product_uom_id": self.unit.id, "lot_id": lot.id,
            "location_id": receipt.location_id.id, "location_dest_id": receipt.location_dest_id.id,
            "step_nursery_net_seed_g": 10.24, "company_id": self.company.id, "picked": True,
        })
        line.action_step_nursery_apply_seed_weight()
        self.assertEqual((line.quantity, line.step_nursery_seed_rate_used), (40, 4))
        receipt.button_validate()
        self.assertEqual(line.state, "done")
        self.assertEqual(line.quantity, 40)
        with self.assertRaises(ValidationError):
            line.action_step_nursery_apply_seed_weight()
