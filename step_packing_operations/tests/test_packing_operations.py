from types import SimpleNamespace
from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user

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
            "name": "Fruta granel T41", "is_storable": True, "weight": 1.0, "grupo_labor": "pack"})
        cls.finished = cls.env["product.product"].create({
            "name": "Caja exportación T41", "default_code": "T41-EXPORT", "is_storable": True, "weight": 5.0, "grupo_labor": "pack"})
        cls.national = cls.env["product.product"].create({
            "name": "Fruta nacional T41", "is_storable": True, "weight": 1.0, "grupo_labor": "pack"})
        cls.carton = cls.env["product.product"].create({
            "name": "Cartón T41", "is_storable": True, "grupo_labor": "pack"})

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

    def test_revision_multi_product_output_created_from_ot(self):
        incoming = self._tag('T41-R2-C', 'C', self.raw, 100, 100)
        incoming.action_step_validate_tag()
        self._stock(self.raw, 100, incoming)
        ot = self.env['step.packing.production'].create({
            'raw_product_id': self.raw.id, 'fruit_grower_id': self.producer.id,
            'fruit_species_id': self.species.id, 'fruit_variety_id': self.variety.id,
            'step_packing_input_tag_ids': [(6, 0, incoming.ids)]})
        action = ot.action_create_export_tag()
        self.assertEqual(action['context']['default_step_packing_production_id'], ot.id)
        export = self._tag('T41-R2-E', 'E', self.finished, 80, 16, 'export')
        national = self._tag('T41-R2-N', 'N', self.national, 15, 15, 'commercial')
        ot.step_packing_output_tag_ids = export | national
        self.env['mrp.bom'].create({'product_tmpl_id': self.finished.product_tmpl_id.id,
            'product_qty': 1, 'bom_line_ids': [(0, 0, {'product_id': self.carton.id, 'product_qty': 1, 'step_export_qty_per_pallet': 2})]})
        self._stock(self.carton, 18)
        ot.action_step_packing_validate()
        ot.action_prepare_materials()
        self.assertEqual(ot.material_line_ids.quantity, 18)
        ot.action_approve_materials()
        ot.action_step_packing_close()
        self.assertFalse(ot.product_id)
        self.assertEqual(ot.state, 'closed')
        self.assertEqual(ot.step_packing_loss_kg, 5)
        self.assertEqual(set(ot.output_picking_id.move_ids.product_id.ids), {self.finished.id, self.national.id})
        self.assertEqual(national.quant_ids.owner_id, self.producer)

    def test_revision_output_create_attaches_and_locks_detail(self):
        ot = self.env['step.packing.production'].create({'fruit_grower_id': self.producer.id,
            'fruit_species_id': self.species.id, 'fruit_variety_id': self.variety.id})
        action = ot.action_create_export_tag()
        tag = self.env['stock.quant.package'].with_context(**action['context']).create({
            'step_tag_line_ids': [(0, 0, {'producer_id': self.producer.id, 'product_id': self.finished.id,
                                        'quantity': 10, 'boxes': 10, 'kilos': 50})]})
        self.assertEqual(ot.step_packing_output_tag_ids, tag)
        self.assertEqual(tag.step_packing_production_id, ot)
        self.assertEqual(tag.step_result_product_id, self.finished)

    def test_revision_reservation_checks_country_at_assignment(self):
        tag = self._tag('T41-R2-RES', 'E', self.finished, 50, 10, 'export')
        tag.action_step_validate_tag()
        self._stock(self.finished, 10, tag)
        country = self.env.ref('base.us')
        reservation = self.env['step.export.stock.reservation'].create({
            'name': 'Reserva mercado T41', 'destination_country_id': country.id,
            'step_package_ids': [(6, 0, tag.ids)]})
        reservation.action_step_reserve()
        self.assertEqual(tag.step_reserved_ids, reservation)
        shipment = self.env['step.export.export'].create({'name': 'Embarque T41 país',
            'destination_country_id': country.id, 'tag_ids': [(6, 0, tag.ids)]})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            shipment.destination_country_id = self.env.ref('base.cl')
        with self.assertRaises(UserError):
            reservation.destination_country_id = self.env.ref('base.cl')
        reservation.action_step_release()
        shipment.destination_country_id = self.env.ref('base.cl')

    def test_revision_repack_preserves_lot_owner_and_source(self):
        self.finished.tracking = 'lot'
        lot = self.env['stock.lot'].create({'name': 'T41-R2-LOT', 'product_id': self.finished.id,
                                         'company_id': self.company.id})
        source = self._tag('T41-R2-SOURCE', 'E', self.finished, 50, 10, 'export')
        source.step_tag_line_ids.lot_id = lot
        source.action_step_validate_tag()
        target = self.env['stock.quant.package'].create({'name': 'T41-R2-TARGET', 'is_fruit_tag': True,
            'step_tag_kind': 'E', 'step_packing_result': 'export', 'especie_id': self.species.id,
            'variedad_id': self.variety.id})
        self.env['stock.quant']._update_available_quantity(self.finished, self.location, 10,
            lot_id=lot, owner_id=self.producer, package_id=source)
        repack = self.env['step.packing.repack'].create({'line_ids': [(0, 0, {
            'source_package_id': source.id, 'target_package_id': target.id,
            'producer_id': self.producer.id, 'product_id': self.finished.id,
            'quantity': 10, 'boxes': 10, 'kilos': 50})]})
        repack.action_validate()
        self.assertEqual(target.step_tag_line_ids.source_package_id, source)
        self.assertEqual(target.step_tag_line_ids.lot_id, lot)
        self.assertEqual(target.quant_ids.owner_id, self.producer)
        self.assertEqual(target.quant_ids.lot_id, lot)

    def test_revision_repack_prepares_destination_from_selected_tags(self):
        source = self._tag('T41-R2-SELECT', 'E', self.finished, 50, 10, 'export')
        source.action_step_validate_tag()
        self._stock(self.finished, 10, source)
        repack = self.env['step.packing.repack'].create({'selected_source_ids': [(6, 0, source.ids)]})
        repack.action_prepare_distribution()
        target = repack.line_ids.target_package_id
        self.assertEqual(target.step_tag_kind, 'E')
        self.assertEqual(target.variedad_id, source.variedad_id)
        repack.action_validate()
        self.assertEqual(target.step_tag_state, 'validated')
        self.assertEqual(repack.source_tag_ids, source)

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
        with self.assertRaises(UserError):
            # La revisión de materiales es obligatoria antes de mover stock.
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
        instruction = self.env['step.packing.instruction'].create({'order_id': order.id, 'name': 'Instructivo QA', 'instruction': '<p>Reservar para exportación</p>'})
        instruction.action_approve()
        reservation.step_instruction_id = instruction
        reservation.action_step_reserve()
        self.assertEqual(reservation.step_reservation_state, "reserved")
        with self.assertRaises(UserError):
            instruction.write({'instruction': '<p>Otra versión</p>'})
        self.assertEqual(reservation.step_picking_id.move_line_ids.package_id, package)
        self.assertEqual(quant._get_available_quantity(self.finished, self.location, package_id=package, strict=True), 0)
        reservation.action_step_release()
        self.assertEqual(reservation.step_picking_id.state, "cancel")
        self.assertEqual(quant._get_available_quantity(self.finished, self.location, package_id=package, strict=True), 10)

    def test_packing_close_moves_real_stock_without_manufacturing(self):
        """El cierre de la OT traslada stock real (MP -> Producción -> PT) con
        traslados de Inventario comunes; en ningún momento se crea ni se exige
        una mrp.production para completar el proceso."""
        existing_manufacturing_ids = set(self.env["mrp.production"].search([]).ids)
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
        self.assertEqual(set(self.env["mrp.production"].search([]).ids),
                         existing_manufacturing_ids)

        production.action_prepare_materials()
        self.assertEqual(production.material_line_ids.quantity, 16)
        with self.assertRaises(UserError):
            production.action_step_packing_close()
        production.action_approve_materials()
        production.action_step_packing_close()

        self.assertEqual(production.state, "closed")
        self.assertEqual(output.step_tag_state, "validated")
        self.assertEqual(incoming.step_tag_state, "processed")
        self.assertEqual(set(self.env["mrp.production"].search([]).ids),
                         existing_manufacturing_ids)
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
        with self.assertRaises(UserError):
            production.action_step_packing_close()

    def test_material_shortage_rolls_back_consumed_fruit(self):
        order = self._order()
        order.action_validate()
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': self.finished.product_tmpl_id.id, 'product_qty': 1,
            'bom_line_ids': [(0, 0, {'product_id': self.carton.id, 'product_qty': 1})],
        })
        incoming = self._tag('QA-SHORT-C', 'C', self.raw, 100, 100)
        incoming.action_step_validate_tag()
        output = self._tag('QA-SHORT-E', 'E', self.finished, 80, 16, 'export')
        self._stock(self.raw, 100, incoming)
        production = self._production(order, incoming, output, bom)
        production.action_step_packing_validate()
        production.action_prepare_materials()
        production.action_approve_materials()
        with self.assertRaises(UserError):
            production.material_line_ids.write({'quantity': 0})
        with self.assertRaises(UserError):
            production.action_step_packing_close()
        self.assertEqual(production.state, 'validated')
        self.assertFalse(production.input_picking_id)
        self.assertEqual(self.env['stock.quant']._get_available_quantity(
            self.raw, self.location, package_id=incoming, strict=True), 100)
        self.assertEqual(incoming.step_tag_state, 'validated')

    def test_material_review_detects_changed_pallet_and_requires_reason(self):
        order = self._order()
        order.action_validate()
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': self.finished.product_tmpl_id.id, 'product_qty': 1,
            'bom_line_ids': [(0, 0, {'product_id': self.carton.id, 'product_qty': 1})],
        })
        incoming = self._tag('QA-REVIEW-C', 'C', self.raw, 100, 100)
        incoming.action_step_validate_tag()
        output = self._tag('QA-REVIEW-E', 'E', self.finished, 80, 16, 'export')
        production = self._production(order, incoming, output, bom)
        production.action_prepare_materials()
        with self.assertRaises(UserError):
            production.material_line_ids.unlink()
        with self.assertRaises(UserError):
            self.env['step.packing.material.consumption'].with_context(_packing_control=True).create({
                'production_id': production.id, 'package_id': output.id, 'product_id': self.carton.id,
                'planned_qty': 1, 'quantity': 1,
            })
        production.action_prepare_materials()
        self.assertEqual(production.material_line_ids.planned_qty, 16)
        production.material_line_ids.quantity = 17
        with self.assertRaises(ValidationError):
            production.action_approve_materials()
        production.material_line_ids.reason = 'Caja dañada'
        operator = new_test_user(self.env, login='qa-packing-operator', groups='stock.group_stock_user')
        with self.assertRaises(UserError):
            production.with_user(operator).action_approve_materials()
        production.action_approve_materials()
        output.step_tag_line_ids.quantity = 15
        production.action_step_packing_validate()
        with self.assertRaises(UserError):
            production.action_step_packing_close()
        with self.assertRaises(UserError):
            production.write({'state': 'closed'})

    def test_effective_hours_and_overlapping_stops(self):
        order = self._order()
        production = self._production(order, self.env['stock.quant.package'], self.env['stock.quant.package'])
        reason = self.env['step.packing.stop.reason'].create({'name': 'Revisión QA'})
        production.write({'workers': 4, 'started_at': '2026-11-09 08:00:00', 'finished_at': '2026-11-09 12:00:00',
                          'downtime_ids': [(0, 0, {'reason_id': reason.id, 'started_at': '2026-11-09 09:00:00', 'finished_at': '2026-11-09 09:30:00'})]})
        self.assertEqual(production.effective_hours, 3.5)
        self.assertEqual(production.idle_percent, 12.5)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env['step.packing.downtime'].create({'production_id': production.id, 'reason_id': reason.id,
                'started_at': '2026-11-09 09:15:00', 'finished_at': '2026-11-09 09:45:00'})

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
                    "product_code": "T41-EXPORT",
                    "quantity": 16, "boxes": 16, "kilos": 80,
                })
            self.assertIn("/report/pdf/", result["report_url"])
            self.assertEqual(len(production.step_packing_output_tag_ids), 1)
            self.assertEqual(production.step_packing_output_tag_ids.step_actual_kg, 80)

    def test_contract_value_monthly_bill_and_national_return(self):
        self.finished.step_export_enabled = True
        category = self.env['product.category'].create({'name': 'Fruta AVCO QA', 'property_cost_method': 'average'})
        self.finished.categ_id = category
        account = self.env['account.account'].search([('company_ids', 'in', self.company.id), ('account_type', '=', 'expense')], limit=1)
        contract = self.env['step.producer.purchase.contract'].create({'partner_id': self.producer.id})
        contract_line = self.env['step.producer.purchase.contract.product'].create({
            'contract_id': contract.id, 'product_id': self.finished.id, 'species_id': self.species.id,
            'quantity': 16, 'uom_id': self.finished.uom_id.id, 'price_unit': 2, 'debit_account_id': account.id})
        self.env['step.producer.purchase.contract.installment'].create({
            'contract_id': contract.id, 'product_line_id': contract_line.id, 'quantity': 16, 'date_due': '2026-11-30'})
        contract.action_confirm()
        bom = self.env['mrp.bom'].create({'product_tmpl_id': self.finished.product_tmpl_id.id, 'product_qty': 1,
            'bom_line_ids': [(0, 0, {'product_id': self.carton.id, 'product_qty': 1})]})
        order = self._order()
        order.action_validate()
        incoming = self._tag('QA-CTR-C', 'C', self.raw, 100, 100)
        incoming.action_step_validate_tag()
        export = self._tag('QA-CTR-E', 'E', self.finished, 80, 16, 'export')
        national = self._tag('QA-CTR-N', 'N', self.national, 20, 20, 'commercial')
        self.env['stock.quant']._update_available_quantity(self.raw, self.location, 100, package_id=incoming, owner_id=self.producer)
        self._stock(self.carton, 16)
        production = self._production(order, incoming, export | national, bom)
        production.write({'contract_id': contract.id, 'date': '2026-11-09', 'required_inspection': 'sag'})
        production.action_step_packing_validate()
        production.action_prepare_materials()
        production.action_approve_materials()
        production.action_step_packing_close()
        self.assertEqual(production.contract_amount, 32)
        self.assertAlmostEqual(sum(production.output_picking_id.move_ids.filtered(lambda row: row.product_id == self.finished).stock_valuation_layer_ids.mapped('value')), 32)
        self.assertEqual(national.quant_ids.filtered(lambda row: row.quantity > 0).owner_id, self.producer)
        shipment = self.env['step.export.export'].create({'name': 'Embarque inspección QA', 'tag_ids': [(6, 0, export.ids)]})
        with self.assertRaises(UserError):
            shipment._check_tag_load()
        inspection = self.env['step.packing.inspection'].create({'name': 'Inspección SAG QA', 'production_id': production.id,
            'kind': 'sag', 'inspector_id': self.producer.id, 'package_ids': [(6, 0, export.ids)]})
        with self.assertRaises(UserError):
            inspection.action_approve()
        inspection.certificate_reference = 'CERTIFICADO-PRUEBA-QA'
        inspection.action_approve()
        shipment._check_tag_load()
        with self.assertRaises(UserError):
            inspection.write({'certificate_reference': 'OTRA-REFERENCIA'})
        rejected = inspection.copy({'name': 'Reevaluación QA', 'certificate_reference': False, 'observations': 'Calidad rechazada QA'})
        rejected.action_reject()
        with self.assertRaises(UserError):
            shipment._check_tag_load()
        self.company.step_packing_purchase_journal_id = self.env['account.journal'].create({
            'name': 'Compra fruta QA', 'code': 'QAFP', 'type': 'purchase', 'company_id': self.company.id})
        wizard = self.env['step.packing.monthly.fruit.bill'].create({'date_start': '2026-11-01', 'date_end': '2026-11-30', 'producer_ids': [(6, 0, self.producer.ids)]})
        action = wizard.action_prepare_bills()
        self.assertEqual(production.purchase_bill_id.state, 'draft')
        self.assertEqual(production.purchase_bill_id.amount_untaxed, 32)
        self.assertEqual(wizard.action_prepare_bills()['domain'], action['domain'])
        production.action_return_national_fruit()
        self.assertEqual(production.return_picking_id.state, 'done')
        self.assertEqual(national.step_tag_state, 'dispatched')
        self.assertEqual(national.quant_ids.filtered(lambda row: row.quantity > 0).location_id.usage, 'customer')
        with self.assertRaises(UserError):
            production.action_return_national_fruit()

    def test_costing_capitalizes_only_owned_export_and_is_idempotent(self):
        expense = self.env['account.account'].search([('company_ids', 'in', self.company.id), ('account_type', '=', 'expense')], limit=1)
        valuation = self.env['account.account'].create({'name': 'Inventario costeo QA', 'code': 'QAT41VAL',
            'account_type': 'asset_current', 'company_ids': [(6, 0, self.company.ids)]})
        journal = self.env['account.journal'].create({'name': 'Valoración costeo QA', 'code': 'QCST', 'type': 'general', 'company_id': self.company.id})
        category = self.env['product.category'].create({'name': 'FIFO costeo QA', 'property_cost_method': 'fifo',
            'property_valuation': 'real_time', 'property_stock_valuation_account_id': valuation.id,
            'property_stock_account_input_categ_id': expense.id, 'property_stock_account_output_categ_id': expense.id,
            'property_stock_journal': journal.id})
        self.finished.categ_id = category
        self.company.lc_journal_id = journal
        service = self.env['product.product'].create({'name': 'Transformación QA', 'type': 'service', 'grupo_labor': 'pack'})
        bom = self.env['mrp.bom'].create({'product_tmpl_id': self.finished.product_tmpl_id.id, 'product_qty': 1,
            'bom_line_ids': [(0, 0, {'product_id': self.carton.id, 'product_qty': 1})]})
        order = self._order()
        order.action_validate()
        incoming = self._tag('QA-COST-C', 'C', self.raw, 100, 100)
        incoming.action_step_validate_tag()
        export = self._tag('QA-COST-E', 'E', self.finished, 80, 16, 'export')
        national = self._tag('QA-COST-N', 'N', self.national, 20, 20, 'commercial')
        self.env['stock.quant']._update_available_quantity(self.raw, self.location, 100, package_id=incoming, owner_id=self.producer)
        self._stock(self.carton, 16)
        production = self._production(order, incoming, export | national, bom)
        production.action_step_packing_validate()
        production.action_prepare_materials()
        production.action_approve_materials()
        production.action_step_packing_close()
        pool = self.env['step.packing.cost.allocation'].create({'name': 'Mano de obra QA', 'production_ids': [(6, 0, production.ids)],
            'amount': 100, 'basis': 'kg', 'product_id': service.id, 'credit_account_id': expense.id, 'source_reference': 'PLANILLA-QA'})
        pool.action_allocate()
        pool.action_allocate()
        self.assertEqual(len(production.cost_ids), 1)
        self.assertAlmostEqual(production.transformation_cost, 100)
        self.assertAlmostEqual(production.capitalizable_cost, 80)
        pool.action_reopen()
        self.assertFalse(production.cost_ids)
        pool.action_allocate()
        production.action_approve_costs()
        with self.assertRaises(UserError):
            pool.action_reopen()
        production.action_reopen_costs()
        self.assertEqual(production.state, 'closed')
        production.action_approve_costs()
        with self.assertRaises(UserError):
            production.cost_ids.write({'amount': 200})
        before = sum(production._export_cost_moves().stock_valuation_layer_ids.mapped('value'))
        production.action_capitalize_costs()
        landed = production.landed_cost_id
        self.assertEqual(landed.state, 'done')
        self.assertEqual(landed.account_move_id.state, 'posted')
        self.assertAlmostEqual(sum(landed.stock_valuation_layer_ids.mapped('value')), 80)
        self.assertAlmostEqual(sum(production._export_cost_moves().stock_valuation_layer_ids.mapped('value')) - before, 80)
        self.assertNotIn(self.national, landed.valuation_adjustment_lines.product_id)
        self.assertEqual(national.quant_ids.filtered(lambda row: row.quantity > 0).owner_id, self.producer)
        production.action_capitalize_costs()
        self.assertEqual(production.landed_cost_id, landed)
        html, _ = self.env['ir.actions.report']._render_qweb_html('step_packing_operations.report_packing_costing', production.ids)
        self.assertIn(b'Costeo de OT', html)
        with self.assertRaises(UserError):
            landed.cost_lines.write({'price_unit': 999})
        with self.assertRaises(UserError):
            production.with_context(_packing_cost=True).write({'landed_cost_id': False})
        with self.assertRaises(UserError):
            production.action_reopen_costs()
        with self.assertRaises(UserError):
            landed.account_move_id.button_draft()
