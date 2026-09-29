from datetime import date

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestProducerDeliveryBalance(TransactionCase):

    def test_preliquidation_projects_pending_fruit_and_cost(self):
        producer = self.env["res.partner"].create({"name": "Productor preliq T38"})
        fundo = self.env["step.fundo"].create({
            "name": "Fundo preliq T38", "partner_id": producer.id,
        })
        season = self.env["step.temporada"].create({"name": "Temporada preliq T38"})
        species = self.env["step.especie"].create({
            "name": "Cereza preliq T38", "type_especie": "frutal", "group_especie": "baya",
        })
        group = self.env["step.grupo.variedad"].create({
            "name": "Grupo preliq T38", "especie_id": species.id,
        })
        variety = self.env["step.variedad"].create({
            "name": "Santina preliq T38", "cod_variedad": "T38-PL-SANTINA",
            "especie_id": species.id, "grupo_variedad_id": group.id,
        })
        product = self.env["product.product"].create({"name": "Fruta preliq T38"})
        self.env["step.producer.preliq.price"].create({
            "name": "Precios preliq T38", "season_id": season.id,
            "species_id": species.id, "valid_from": "2026-07-01",
            "valid_to": "2026-12-31",
            "line_ids": [(0, 0, {
                "variety_id": variety.id,
                "uom_id": self.env.ref("uom.product_uom_kgm").id,
                "price": 5.5, "estimated_cost_usd_per_kg": 2.5,
                "cost_confirmed": True,
            })],
        })
        estimate = self.env["step.export.estimate"].create({
            "name": "Estimación preliq T38", "producer_id": producer.id,
            "fundo_id": fundo.id, "season_id": season.id,
            "estimate_line_ids": [(0, 0, {
                "delivery_kind": "process", "species_id": species.id,
                "variety_id": variety.id, "product_id": product.id,
                "export_kg": 100, "export_percentage": 0.8,
                "kg_per_box": 10, "boxes_per_package": 10,
            })],
        })
        estimate.state = "current"
        simulation = self.env["step.producer.preliquidation"].create({
            "producer_id": producer.id, "season_id": season.id,
            "species_id": species.id, "date": "2026-09-29",
        })
        simulation.action_generate()
        self.assertEqual(simulation.state, "generated")
        self.assertEqual(len(simulation.line_ids), 1)
        self.assertAlmostEqual(simulation.line_ids.source_kg, 125)
        self.assertAlmostEqual(simulation.line_ids.export_kg, 100)
        self.assertAlmostEqual(simulation.estimated_return_usd, 300)
        self.assertAlmostEqual(simulation.projected_balance_usd, 300)
        accountant = self.env["res.users"].create({
            "name": "Contable preliq T38", "login": "t38-preliq-accountant",
            "groups_id": [(6, 0, [self.env.ref("account.group_account_user").id])],
        })
        with self.assertRaises(AccessError):
            simulation.line_ids.with_user(accountant).write({"return_usd": 1000})

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

        settlement.producer_settlement_ids.unlink()
        second_tag = self.env["stock.quant.package"].create({
            "name": "T38-FOB-SEGUNDA", "is_fruit_tag": True, "step_tag_kind": "E",
            "step_tag_line_ids": [(0, 0, {
                "producer_id": producer_b.id, "product_id": product.id,
                "quantity": 10, "kilos": 100,
            })],
        })
        second_shipment = self.env["step.export.export"].create({
            "name": "Embarque pool T38", "sales_program_id": program.id,
            "date": date(2026, 11, 4), "tag_ids": [(4, second_tag.id)],
            "line_ids": [(0, 0, {
                "product_id": product.id, "pallet_qty": 1,
                "boxes_per_pallet": 10, "kg_per_box": 10,
            })],
        })
        second_invoice = self.env["account.move"].create({
            "move_type": "out_invoice", "partner_id": receiver.id,
            "step_export_shipment_id": second_shipment.id,
        })
        settlement.write({
            "producer_price_mode": "pool",
            "line_ids": [(0, 0, {
                "shipment_id": second_shipment.id, "invoice_id": second_invoice.id,
                "sales_amount": 3000,
            })],
        })
        settlement._generate_producer_settlements()
        pooled = settlement.producer_settlement_ids.mapped("line_ids")
        self.assertAlmostEqual(sum(pooled.mapped("allocated_fob_usd")), 4000)
        self.assertAlmostEqual(sum(pooled.filtered(
            lambda line: line.settlement_id.producer_id == producer_a
        ).mapped("allocated_fob_usd")), 1200)
        self.assertAlmostEqual(sum(pooled.filtered(
            lambda line: line.settlement_id.producer_id == producer_b
        ).mapped("allocated_fob_usd")), 2800)

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
