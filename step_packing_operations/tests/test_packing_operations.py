from types import SimpleNamespace
from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from ..controllers import mobile


@tagged("post_install", "-at_install", "step_packing_operations")
class TestPackingOperations(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.producer = cls.env["res.partner"].create({"name": "Productor Packing T41"})
        cls.species = cls.env["step.especie"].create({
            "name": "Cereza Packing T41", "type_especie": "frutal", "group_especie": "fruta_h"})
        cls.variety_group = cls.env["step.grupo.variedad"].create({
            "name": "Grupo T41", "especie_id": cls.species.id})
        cls.variety = cls.env["step.variedad"].create({
            "name": "Santina T41", "cod_variedad": "T41S", "especie_id": cls.species.id,
            "grupo_variedad_id": cls.variety_group.id})
        cls.raw = cls.env["product.product"].create({
            "name": "Fruta granel T41", "is_storable": True, "weight": 1.0})
        cls.finished = cls.env["product.product"].create({
            "name": "Caja exportación T41", "is_storable": True, "weight": 5.0})
        cls.national = cls.env["product.product"].create({
            "name": "Fruta nacional T41", "is_storable": True, "weight": 1.0})
        cls.carton = cls.env["product.product"].create({
            "name": "Cartón T41", "is_storable": True})

    def _order(self, forbidden=False):
        return self.env["step.packing.order"].create({
            "week_start": "2026-11-09", "week_end": "2026-11-15",
            "forbidden_producer_ids": [(6, 0, self.producer.ids)] if forbidden else [],
            "line_ids": [(0, 0, {
                "product_id": self.finished.id, "species_id": self.species.id,
                "variety_id": self.variety.id, "boxes": 100, "kilos": 500,
            })],
        })

    def _tag(self, name, kind, product, kilos, boxes, result=False):
        return self.env["stock.quant.package"].create({
            "name": name, "is_fruit_tag": True, "step_tag_kind": kind,
            "step_packing_result": result, "step_producer_id": self.producer.id,
            "especie_id": self.species.id, "variedad_id": self.variety.id,
            "step_tag_line_ids": [(0, 0, {
                "producer_id": self.producer.id, "product_id": product.id,
                "quantity": boxes, "boxes": boxes, "kilos": kilos,
            })],
        })

    def _production(self, order, inputs, outputs):
        return self.env["mrp.production"].create({
            "product_id": self.finished.id, "product_qty": 100,
            "product_uom_id": self.finished.uom_id.id,
            "step_packing_order_id": order.id,
            "step_packing_input_tag_ids": [(6, 0, inputs.ids)],
            "step_packing_output_tag_ids": [(6, 0, outputs.ids)],
        })

    def test_order_material_needs_and_creation(self):
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": self.finished.product_tmpl_id.id,
            "product_id": self.finished.id, "product_qty": 1,
            "bom_line_ids": [(0, 0, {"product_id": self.carton.id, "product_qty": 1})],
        })
        order = self._order()
        order.line_ids.bom_id = bom
        order.action_refresh_materials()
        self.assertEqual(order.material_need_ids.product_id, self.carton)
        self.assertEqual(order.material_need_ids.required_qty, 100)
        order.action_validate()
        action = order.line_ids.action_create_production()
        self.assertEqual(self.env["mrp.production"].browse(action["res_id"]).step_packing_order_id, order)
        with self.assertRaises(UserError):
            order.write({"week_end": "2026-11-16"})

    def test_balance_and_restrictions(self):
        order = self._order()
        order.action_validate()
        incoming = self._tag("T41-C-1", "C", self.raw, 1000, 100)
        incoming.action_step_validate_tag()
        export = self._tag("T41-E-1", "E", self.finished, 800, 160, "export")
        national = self._tag("T41-N-1", "N", self.national, 100, 100, "commercial")
        production = self._production(order, incoming, export | national)
        self.assertEqual(production.step_packing_loss_kg, 100)
        production.action_step_packing_validate()
        self.assertEqual(production.step_packing_state, "validated")
        self.assertEqual(production.fruit_grower_id, self.producer)
        with self.assertRaises(UserError):
            production.action_step_packing_close()

    def test_overproduction_and_forbidden_producer(self):
        order = self._order(forbidden=True)
        order.action_validate()
        incoming = self._tag("T41-C-2", "C", self.raw, 100, 10)
        incoming.action_step_validate_tag()
        export = self._tag("T41-E-2", "E", self.finished, 110, 22, "export")
        production = self._production(order, incoming, export)
        with self.assertRaises(ValidationError):
            production.action_step_packing_validate()
        export.step_tag_line_ids.kilos = 90
        with self.assertRaises(ValidationError):
            production.action_step_packing_validate()

    def test_repack_moves_quant_between_packages(self):
        source = self._tag("T41-REPACK-S", "E", self.finished, 50, 10, "export")
        source.action_step_validate_tag()
        target = self.env["stock.quant.package"].create({
            "name": "T41-REPACK-T", "is_fruit_tag": True, "step_tag_kind": "E",
            "step_packing_result": "export", "especie_id": self.species.id,
            "variedad_id": self.variety.id,
        })
        warehouse = self.env["stock.warehouse"].search([
            ("company_id", "=", self.company.id)], limit=1)
        location = warehouse.lot_stock_id
        quant = self.env["stock.quant"]
        quant._update_available_quantity(self.finished, location, 10, package_id=source)
        repack = self.env["step.packing.repack"].create({
            "line_ids": [(0, 0, {
                "source_package_id": source.id, "target_package_id": target.id,
                "producer_id": self.producer.id, "product_id": self.finished.id,
                "quantity": 10, "boxes": 10, "kilos": 50,
            })],
        })
        repack.action_validate()
        self.assertEqual(repack.picking_id.state, "done")
        self.assertEqual(source.step_tag_state, "repalletized")
        self.assertEqual(target.step_tag_state, "validated")
        self.assertEqual(quant._get_available_quantity(self.finished, location, package_id=source, strict=True), 0)
        self.assertEqual(quant._get_available_quantity(self.finished, location, package_id=target, strict=True), 10)

    def test_repack_mixed_target_keeps_producer_detail(self):
        other = self.env["res.partner"].create({"name": "Segundo productor T41"})
        first = self._tag("T41-MIX-S1", "E", self.finished, 50, 10, "export")
        second = self._tag("T41-MIX-S2", "E", self.finished, 25, 5, "export")
        second.step_tag_line_ids.producer_id = other
        second.step_producer_id = other
        first.action_step_validate_tag()
        second.action_step_validate_tag()
        target = self.env["stock.quant.package"].create({
            "name": "T41-MIX-T", "is_fruit_tag": True, "step_tag_kind": "E",
            "step_packing_result": "export", "especie_id": self.species.id,
            "variedad_id": self.variety.id,
        })
        warehouse = self.env["stock.warehouse"].search([
            ("company_id", "=", self.company.id)], limit=1)
        location = warehouse.lot_stock_id
        quant = self.env["stock.quant"]
        quant._update_available_quantity(self.finished, location, 10, package_id=first)
        quant._update_available_quantity(self.finished, location, 5, package_id=second)
        repack = self.env["step.packing.repack"].create({
            "line_ids": [
                (0, 0, {"source_package_id": first.id, "target_package_id": target.id,
                        "producer_id": self.producer.id, "product_id": self.finished.id,
                        "quantity": 10, "boxes": 10, "kilos": 50}),
                (0, 0, {"source_package_id": second.id, "target_package_id": target.id,
                        "producer_id": other.id, "product_id": self.finished.id,
                        "quantity": 5, "boxes": 5, "kilos": 25}),
            ],
        })
        repack.action_validate()
        self.assertEqual(target.step_composition, "mixed")
        self.assertEqual(set(target.step_tag_line_ids.mapped("producer_id").ids), {self.producer.id, other.id})
        self.assertEqual(quant._get_available_quantity(self.finished, location, package_id=target, strict=True), 15)

    def test_reservation_blocks_and_releases_tag_stock(self):
        order = self._order()
        order.action_validate()
        package = self._tag("T41-RESERVE", "E", self.finished, 50, 10, "export")
        package.action_step_validate_tag()
        warehouse = self.env["stock.warehouse"].search([
            ("company_id", "=", self.company.id)], limit=1)
        location = warehouse.lot_stock_id
        quant = self.env["stock.quant"]
        quant._update_available_quantity(self.finished, location, 10, package_id=package)
        reservation = self.env["step.export.stock.reservation"].create({
            "name": "T41 reserva especial", "step_packing_order_id": order.id,
            "step_package_ids": [(6, 0, package.ids)],
        })
        reservation.action_step_reserve()
        self.assertEqual(reservation.step_reservation_state, "reserved")
        self.assertEqual(reservation.step_picking_id.move_line_ids.package_id, package)
        self.assertEqual(quant._get_available_quantity(self.finished, location, package_id=package, strict=True), 0)
        reservation.action_step_release()
        self.assertEqual(reservation.step_picking_id.state, "cancel")
        self.assertEqual(quant._get_available_quantity(self.finished, location, package_id=package, strict=True), 10)

    def test_manufacturing_close_checks_real_packages(self):
        order = self._order()
        order.action_validate()
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": self.finished.product_tmpl_id.id,
            "product_id": self.finished.id, "product_qty": 16,
            "bom_line_ids": [(0, 0, {"product_id": self.raw.id, "product_qty": 100})],
        })
        incoming = self._tag("T41-MO-C", "C", self.raw, 100, 100)
        incoming.action_step_validate_tag()
        output = self._tag("T41-MO-E", "E", self.finished, 80, 16, "export")
        warehouse = self.env["stock.warehouse"].search([
            ("company_id", "=", self.company.id)], limit=1)
        quant = self.env["stock.quant"]
        quant._update_available_quantity(self.raw, warehouse.lot_stock_id, 100, package_id=incoming)
        production = self.env["mrp.production"].create({
            "product_id": self.finished.id, "product_qty": 16,
            "product_uom_id": self.finished.uom_id.id,
            "bom_id": bom.id, "step_packing_order_id": order.id,
            "step_packing_input_tag_ids": [(6, 0, incoming.ids)],
            "step_packing_output_tag_ids": [(6, 0, output.ids)],
        })
        production.action_step_packing_validate()
        production.action_confirm()
        production.action_assign()
        self.assertEqual(production.move_raw_ids.move_line_ids.package_id, incoming)
        production.qty_producing = 16
        production.move_finished_ids.quantity = 16
        production.move_finished_ids.move_line_ids.result_package_id = output
        production.move_raw_ids.picked = True
        result = production.button_mark_done()
        self.assertEqual(production.state, "done", result)
        production.action_step_packing_close()
        self.assertEqual(production.step_packing_state, "closed")
        self.assertEqual(output.step_tag_state, "validated")
        self.assertEqual(incoming.step_tag_state, "processed")
        self.assertEqual(quant._get_available_quantity(self.finished, warehouse.lot_stock_id,
                         package_id=output, strict=True), 16)
        html, _ = self.env["ir.actions.report"]._render_qweb_html(
            "step_packing_operations.report_packing_process", production.ids)
        self.assertIn(b"Informe de proceso de Packing", html)

    def test_mobile_scan_is_idempotent(self):
        order = self._order()
        order.action_validate()
        production = self._production(order, self.env["stock.quant.package"], self.env["stock.quant.package"])
        production.write({
            "fruit_grower_id": self.producer.id,
            "fruit_species_id": self.species.id,
            "fruit_variety_id": self.variety.id,
        })
        harvest = self._tag("T41-MOB-C", "C", self.raw, 100, 10)
        harvest.action_step_validate_tag()
        controller = mobile.PackingMobile()
        with patch.object(mobile, "request", SimpleNamespace(env=self.env)):
            controller._scan({"production_id": production.id, "code": harvest.name, "kind": "C"})
            self.assertEqual(production.step_packing_input_tag_ids, harvest)
            for _ in range(2):
                result = controller._scan({
                    "production_id": production.id, "code": "T41-MOB-E", "kind": "E",
                    "quantity": 16, "boxes": 16, "kilos": 80,
                })
            self.assertIn("/report/pdf/", result["report_url"])
            self.assertEqual(len(production.step_packing_output_tag_ids), 1)
            self.assertEqual(production.step_packing_output_tag_ids.step_actual_kg, 80)
