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
        cls.warehouse = cls.env["stock.warehouse"].search([("company_id", "=", cls.company.id)], limit=1)
        cls.location = cls.warehouse.lot_stock_id
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

    def _stock(self, product, qty, package=False):
        self.env["stock.quant"]._update_available_quantity(product, self.location, qty, package_id=package or None)

    def _production(self, order, inputs, outputs, bom=False):
        vals = {
            "product_id": self.finished.id, "product_qty": 100,
            "product_uom_id": self.finished.uom_id.id,
            "step_packing_order_id": order.id,
            "step_packing_input_tag_ids": [(6, 0, inputs.ids)],
            "step_packing_output_tag_ids": [(6, 0, outputs.ids)],
        }
        if bom:
            vals["bom_id"] = bom.id
        return self.env["step.packing.production"].create(vals)

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
        production = self.env["step.packing.production"].browse(action["res_id"])
        self.assertEqual(action["res_model"], "step.packing.production")
        self.assertEqual(production.step_packing_order_id, order)
        self.assertEqual(production.bom_id, bom)
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
        self.assertEqual(production.state, "validated")
        self.assertEqual(production.fruit_grower_id, self.producer)
        with self.assertRaises(ValidationError):
            # No hay existencias reales detrás de las tarjas: el cierre debe
            # fallar por falta de stock, no por depender de Fabricación.
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
        self._stock(self.finished, 10, source)
        quant = self.env["stock.quant"]
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
        self.assertEqual(quant._get_available_quantity(self.finished, self.location, package_id=source, strict=True), 0)
        self.assertEqual(quant._get_available_quantity(self.finished, self.location, package_id=target, strict=True), 10)

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
        self._stock(self.finished, 10, first)
        self._stock(self.finished, 5, second)
        quant = self.env["stock.quant"]
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
        self.assertEqual(quant._get_available_quantity(self.finished, self.location, package_id=target, strict=True), 15)

    def test_reservation_blocks_and_releases_tag_stock(self):
        order = self._order()
        order.action_validate()
        package = self._tag("T41-RESERVE", "E", self.finished, 50, 10, "export")
        package.action_step_validate_tag()
        self._stock(self.finished, 10, package)
        quant = self.env["stock.quant"]
        reservation = self.env["step.export.stock.reservation"].create({
            "name": "T41 reserva especial", "step_packing_order_id": order.id,
            "step_package_ids": [(6, 0, package.ids)],
        })
        reservation.action_step_reserve()
        self.assertEqual(reservation.step_reservation_state, "reserved")
        self.assertEqual(reservation.step_picking_id.move_line_ids.package_id, package)
        self.assertEqual(quant._get_available_quantity(self.finished, self.location, package_id=package, strict=True), 0)
        reservation.action_step_release()
        self.assertEqual(reservation.step_picking_id.state, "cancel")
        self.assertEqual(quant._get_available_quantity(self.finished, self.location, package_id=package, strict=True), 10)

    def test_packing_close_moves_real_stock_without_manufacturing(self):
        """El cierre de la OT traslada stock real (MP -> Producción -> PT) con
        traslados de Inventario comunes; en ningún momento se crea ni se exige
        una mrp.production para completar el proceso."""
        order = self._order()
        order.action_validate()
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": self.finished.product_tmpl_id.id,
            "product_id": self.finished.id, "product_qty": 16,
            "bom_line_ids": [(0, 0, {"product_id": self.carton.id, "product_qty": 16})],
        })
        incoming = self._tag("T41-MO-C", "C", self.raw, 100, 100)
        incoming.action_step_validate_tag()
        output = self._tag("T41-MO-E", "E", self.finished, 80, 16, "export")
        self._stock(self.raw, 100, incoming)
        self._stock(self.carton, 16)
        production = self._production(order, incoming, output, bom=bom)
        production.action_step_packing_validate()
        self.assertFalse(self.env["mrp.production"].search([("step_packing_order_id", "=", order.id)]))

        production.action_step_packing_close()

        self.assertEqual(production.state, "closed")
        self.assertEqual(output.step_tag_state, "validated")
        self.assertEqual(incoming.step_tag_state, "processed")
        self.assertFalse(self.env["mrp.production"].search([]))
        self.assertEqual(production.input_picking_id.state, "done")
        self.assertEqual(production.output_picking_id.state, "done")
        self.assertEqual(production.material_picking_id.state, "done")
        quant = self.env["stock.quant"]
        self.assertEqual(quant._get_available_quantity(self.finished, self.location, package_id=output, strict=True), 16)
        self.assertEqual(quant._get_available_quantity(self.raw, self.location, package_id=incoming, strict=True), 0)
        self.assertEqual(quant._get_available_quantity(self.carton, self.location), 0)
        html, _ = self.env["ir.actions.report"]._render_qweb_html(
            "step_packing_operations.report_packing_process", production.ids)
        self.assertIn(b"Informe de proceso de Packing", html)

    def test_packing_close_without_stock_fails(self):
        order = self._order()
        order.action_validate()
        incoming = self._tag("T41-NOSTOCK-C", "C", self.raw, 100, 100)
        incoming.action_step_validate_tag()
        output = self._tag("T41-NOSTOCK-E", "E", self.finished, 80, 16, "export")
        production = self._production(order, incoming, output)
        production.action_step_packing_validate()
        with self.assertRaises(ValidationError):
            production.action_step_packing_close()

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
