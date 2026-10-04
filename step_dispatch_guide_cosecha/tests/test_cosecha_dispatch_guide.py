from odoo import Command
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "step_dispatch_guide_cosecha")
class TestCosechaDispatchGuide(TransactionCase):
    def test_guide_from_harvest_reception(self):
        fruit = self.env["product.template"].create({"name": "Cereza T25", "is_fruta": True})
        packaging = self.env["product.packaging"].create({
            "name": "Bin T25", "product_id": fruit.product_variant_id.id, "qty": 400})
        reception = self.env["step.cosecha.recepcion"].create({
            "name": "Recepción cosecha T25",
            "recep_line": [Command.create({
                "product_id": fruit.id, "packaging_id": packaging.id, "quantity": 2400,
                "boxes": 6, "tarja": "TJ-25",
            })],
        })
        action = reception.action_create_dispatch_guide()
        carrier = self.env["res.partner"].create({"name": "Transporte T25", "step_carga": True})
        driver = self.env["res.partner"].create({"name": "Chofer T25", "step_chofer": True})
        guide = self.env["step.dispatch.guide"].with_context(**action["context"]).create({
            "external_folio": "C-25", "carrier_id": carrier.id,
            "driver_partner_id": driver.id, "truck_plate": "JH8784",
        })
        self.assertEqual(guide.cosecha_recepcion_id, reception)
        self.assertEqual(guide.transfer_reason_id.code, "5")
        self.assertEqual(guide.total_kilos, 2400)
        self.assertEqual(guide.total_bins, 6)
        self.assertIn("TJ-25", guide.line_ids.description)
        self.assertEqual(guide.line_ids.packaging_id, packaging)
        self.assertEqual(reception.dispatch_guide_count, 1)
        guide.action_confirm()
        self.assertEqual(guide.invoice_status, "no")

    def test_reception_without_lines(self):
        reception = self.env["step.cosecha.recepcion"].create({"name": "Vacía T25"})
        with self.assertRaises(UserError):
            reception.action_create_dispatch_guide()
