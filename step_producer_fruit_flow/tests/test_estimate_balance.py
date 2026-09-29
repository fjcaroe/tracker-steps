from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestProducerDeliveryBalance(TransactionCase):

    def test_receiver_fob_is_split_across_mixed_tag(self):
        producer_a = self.env["res.partner"].create({"name": "FOB A T38"})
        producer_b = self.env["res.partner"].create({"name": "FOB B T38"})
        receiver = self.env["res.partner"].create({"name": "Recibidor T38"})
        season = self.env["step.temporada"].create({"name": "Temporada FOB T38"})
        species = self.env["step.especie"].create({
            "name": "Cereza FOB T38", "type_especie": "frutal", "group_especie": "baya",
        })
        product = self.env["product.product"].create({"name": "Fruta FOB T38"})
        package_type = self.env["stock.package.type"].create({"name": "Pallet FOB T38"})
        program = self.env["step.export.sales.program"].create({
            "name": "Programa FOB T38", "partner_id": receiver.id,
            "season_id": season.id, "species_id": species.id,
            "product_id": product.id, "package_type_id": package_type.id,
            "date_start": date(2026, 11, 2), "date_end": date(2026, 11, 9),
            "pallets_per_container": 1, "boxes_per_pallet": 10,
            "kg_per_box": 10, "rate_to_usd": 1,
        })
        shipment = self.env["step.export.export"].create({
            "name": "Embarque FOB T38", "sales_program_id": program.id,
            "date": date(2026, 11, 3),
            "line_ids": [(0, 0, {
                "product_id": product.id, "pallet_qty": 1,
                "boxes_per_pallet": 10, "kg_per_box": 10,
            })],
        })
        tag = self.env["stock.quant.package"].create({
            "name": "T38-FOB-MIXTA", "is_fruit_tag": True, "step_tag_kind": "E",
            "step_tag_line_ids": [(0, 0, {
                "producer_id": producer_a.id, "product_id": product.id,
                "quantity": 6, "kilos": 60,
            }), (0, 0, {
                "producer_id": producer_b.id, "product_id": product.id,
                "quantity": 4, "kilos": 40,
            })],
        })
        shipment.tag_ids = tag
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice", "partner_id": receiver.id,
            "step_export_shipment_id": shipment.id,
        })
        settlement = self.env["step.export.receiver.settlement"].create({
            "receiver_id": receiver.id, "sales_program_id": program.id,
            "date": date(2026, 11, 20), "rate_to_usd": 1,
            "line_ids": [(0, 0, {
                "shipment_id": shipment.id, "invoice_id": invoice.id,
                "sales_amount": 1000,
            })],
        })
        settlement._generate_producer_settlements()
        lines = settlement.producer_settlement_ids.mapped("line_ids")
        by_producer = {line.settlement_id.producer_id.id: line for line in lines}
        self.assertEqual(set(by_producer), {producer_a.id, producer_b.id})
        self.assertAlmostEqual(by_producer[producer_a.id].kg_qty, 60)
        self.assertAlmostEqual(by_producer[producer_b.id].kg_qty, 40)
        self.assertAlmostEqual(by_producer[producer_a.id].allocated_fob_usd, 600)
        self.assertAlmostEqual(by_producer[producer_b.id].allocated_fob_usd, 400)

    def test_mixed_tag_allocates_measured_kilos_by_producer(self):
        producer_a = self.env["res.partner"].create({"name": "Productor A T38"})
        producer_b = self.env["res.partner"].create({"name": "Productor B T38"})
        product = self.env["product.product"].create({"name": "Fruta mixta T38"})
        tag = self.env["stock.quant.package"].create({
            "name": "T38-MIXTA", "is_fruit_tag": True, "step_tag_kind": "E",
            "step_tag_line_ids": [(0, 0, {
                "producer_id": producer_a.id, "product_id": product.id,
                "quantity": 6, "kilos": 60,
            }), (0, 0, {
                "producer_id": producer_b.id, "product_id": product.id,
                "quantity": 4, "kilos": 40,
            })],
        })
        tag.action_step_validate_tag()
        self.assertEqual(tag._step_liquidation_kg(), 100)
        self.assertEqual(dict((partner.id, share) for partner, share in
                              tag._step_producer_shares()),
                         {producer_a.id: 0.6, producer_b.id: 0.4})

    def test_pending_balance_and_manual_close(self):
        producer = self.env["res.partner"].create({"name": "Productor flujo T38"})
        fundo = self.env["step.fundo"].create({
            "name": "Fundo flujo T38", "partner_id": producer.id,
        })
        season = self.env["step.temporada"].create({"name": "Temporada flujo T38"})
        species = self.env["step.especie"].create({
            "name": "Cereza flujo T38", "type_especie": "frutal", "group_especie": "baya",
        })
        product = self.env["product.product"].create({"name": "Fruta flujo T38"})
        estimate = self.env["step.export.estimate"].create({
            "name": "Estimación flujo T38", "fundo_id": fundo.id,
            "season_id": season.id, "producer_id": producer.id,
            "estimate_line_ids": [(0, 0, {
                "delivery_kind": "packed", "species_id": species.id,
                "product_id": product.id, "export_kg": 100,
            })],
        })
        line = estimate.estimate_line_ids
        self.assertEqual(line.step_received_kg, 0)
        self.assertEqual(line.step_pending_kg, 100)
        with self.assertRaises(UserError):
            line.action_step_close_delivery()
        estimate.state = "current"
        line.action_step_close_delivery()
        self.assertTrue(line.step_delivery_closed)
        self.assertEqual(line.step_pending_kg, 100)
