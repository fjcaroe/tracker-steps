from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestDispatchGuide(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Receptor Citripal", "vat": "76123456-7"})
        cls.carrier = cls.env["res.partner"].create({"name": "Transportes Sur", "vat": "76999999-9", "supplier_rank": 1})
        cls.driver = cls.env["step.dispatch.driver"].create({"name": "Juan Pérez", "vat": "12345678-5"})
        cls.product = cls.env["product.product"].create({"name": "Bins de fruta"})

    def _guide(self, folio="309"):
        return self.env["step.dispatch.guide"].create({
            "external_folio": folio, "partner_id": self.partner.id,
            "origin_address": "Fundo Norte", "destination_address": "Packing Central",
            "transfer_reason": "Traslado de fruta", "carrier_id": self.carrier.id,
            "driver_id": self.driver.id, "truck_plate": "ABCD12",
            "line_ids": [Command.create({"product_id": self.product.id,
                "description": "Bins de fruta", "product_uom_id": self.product.uom_id.id,
                "quantity": 10, "price_unit": 2500, "bin_count": 10, "quantity_kg": 5000})],
        })

    def test_totals_and_confirmation_in_third_party_mode(self):
        guide = self._guide()
        self.assertEqual(guide.total_bins, 10)
        self.assertEqual(guide.total_kilos, 5000)
        self.assertEqual(guide.amount_untaxed, 25000)
        guide.action_confirm()
        self.assertEqual(guide.state, "confirmed")

    def test_external_folio_is_unique_per_company(self):
        self._guide()
        with self.assertRaises(Exception), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self._guide()

    def test_odoo_dte_mode_is_not_silently_emitted(self):
        self.env.company.dispatch_dte_provider = "odoo"
        with self.assertRaises(UserError):
            self._guide().action_confirm()

    def test_negative_quantity_is_rejected(self):
        guide = self._guide()
        with self.assertRaises(ValidationError):
            guide.line_ids.quantity = -1
