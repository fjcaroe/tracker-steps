from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install", "step_dispatch_guide")
class TestDispatchGuide(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.dispatch_dte_provider = "third_party"
        cls.partner = cls.env["res.partner"].create({"name": "Multifruta T25", "street": "Ruta 5 Sur km 38"})
        cls.other_partner = cls.env["res.partner"].create({"name": "Otro cliente T25"})
        cls.carrier = cls.env["res.partner"].create({"name": "Transportes Sur T25", "step_carga": True})
        cls.driver = cls.env["res.partner"].create({"name": "Javier Reyes T25", "step_chofer": True})
        cls.product = cls.env["product.product"].create({"name": "Mandarinas T25", "list_price": 500})
        cls.tax = cls.env["account.tax"].create({
            "name": "IVA 19% T25", "amount": 19, "amount_type": "percent", "type_tax_use": "sale",
        })
        cls.reason_sale = cls.env.ref("step_dispatch_guide.transfer_reason_1")
        cls.reason_internal = cls.env.ref("step_dispatch_guide.transfer_reason_5")
        cls.route = cls.env["x_tramo_de_flete"].create({
            "x_name": "Hijuelas - Buin T25", "origin": "Hijuelas", "destination": "Buin"})
        cls.type_no_freight = cls.env["x_tipo_despacho"].create({"x_name": "Retira cliente T25", "paga_flete": "no"})
        cls.type_freight = cls.env["x_tipo_despacho"].create({"x_name": "Despacho a cliente T25", "paga_flete": "si"})
        cls.vehicle = cls.env["fleet.vehicle"].create({
            "model_id": cls.env["fleet.vehicle.model"].create({
                "name": "Camión T25",
                "brand_id": cls.env["fleet.vehicle.model.brand"].create({"name": "Marca T25"}).id,
            }).id,
            "license_plate": "YK4551",
        })

    def _guide(self, folio="309", partner=None, reason=None, taxed=True, **extra):
        vals = {
            "external_folio": folio, "partner_id": (partner or self.partner).id,
            "transfer_reason_id": (reason or self.reason_sale).id,
            "origin_address": "Fundo El Rayo", "destination_address": "Packing Buin",
            "carrier_id": self.carrier.id, "driver_partner_id": self.driver.id, "truck_plate": "ABCD12",
            "line_ids": [
                Command.create({"product_id": self.product.id, "description": "Mandarinas sector 1A",
                                "product_uom_id": self.product.uom_id.id, "quantity": 10, "price_unit": 1000,
                                "bin_count": 6, "quantity_kg": 2455,
                                "tax_ids": [Command.set(self.tax.ids)] if taxed else False}),
                Command.create({"product_id": self.product.id, "description": "Mandarinas exentas",
                                "product_uom_id": self.product.uom_id.id, "quantity": 2, "price_unit": 500,
                                "bin_count": 32, "quantity_kg": 12549}),
            ],
        }
        vals.update(extra)
        return self.env["step.dispatch.guide"].create(vals)

    def test_totals_follow_design(self):
        guide = self._guide()
        self.assertEqual(guide.total_bins, 38)
        self.assertEqual(guide.total_kilos, 15004)
        self.assertEqual(guide.amount_untaxed, 10000)
        self.assertEqual(guide.amount_exempt, 1000)
        self.assertEqual(guide.amount_tax, 1900)
        self.assertEqual(guide.amount_total, 12900)
        self.assertEqual(guide.tax_rate, 19)

    def test_confirm_in_third_party_mode(self):
        guide = self._guide()
        guide.action_confirm()
        self.assertEqual(guide.state, "confirmed")
        self.assertEqual(guide.invoice_status, "to_invoice")

    def test_confirm_requires_reason_and_driver(self):
        guide = self._guide(driver_partner_id=False)
        with self.assertRaisesRegex(UserError, "Chofer"):
            guide.action_confirm()
        guide = self._guide(folio="310", transfer_reason_id=False)
        with self.assertRaisesRegex(UserError, "Razón del traslado"):
            guide.action_confirm()

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
            guide.line_ids[0].quantity = -1

    def test_dispatch_type_freight_rule(self):
        with self.assertRaisesRegex(ValidationError, "no paga flete"):
            self._guide(dispatch_type_id=self.type_no_freight.id, freight_paid=True)
        guide = self._guide(folio="311", dispatch_type_id=self.type_freight.id)
        with self.assertRaisesRegex(UserError, "paga flete"):
            guide.action_confirm()

    def test_freight_paid_creates_freight_order(self):
        guide = self._guide(freight_paid=True, freight_route_id=self.route.id, vehicle_id=self.vehicle.id)
        self.assertEqual(guide.truck_plate, "YK4551")
        guide.action_confirm()
        order = guide.freight_order_id
        self.assertTrue(order)
        self.assertEqual(order.route_id, self.route)
        self.assertEqual(order.x_studio_transportista, self.carrier)
        self.assertEqual(order.vehicle_id, self.vehicle)
        self.assertEqual(order.dispatch_guide_ids, guide)

    def test_freight_paid_requires_route(self):
        guide = self._guide(freight_paid=True)
        with self.assertRaisesRegex(UserError, "tramo"):
            guide.action_confirm()

    def test_invoice_several_guides_of_same_customer(self):
        guides = self._guide("401") | self._guide("402")
        guides.action_confirm()
        action = guides.action_create_invoice()
        invoice = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(invoice.move_type, "out_invoice")
        self.assertEqual(invoice.partner_id, self.partner)
        self.assertEqual(len(invoice.invoice_line_ids), 4)
        self.assertEqual(guides.mapped("invoice_status"), ["invoiced", "invoiced"])
        self.assertEqual(invoice.dispatch_guide_count, 2)
        self.assertIn("401", invoice.invoice_origin)
        self.assertAlmostEqual(invoice.amount_total, 2 * 12900)
        if "l10n_cl_reference_ids" in invoice._fields:
            self.assertEqual(sorted(invoice.l10n_cl_reference_ids.mapped("origin_doc_number")), ["401", "402"])
        with self.assertRaises(UserError):
            guides[0].action_cancel()
        with self.assertRaises(UserError):
            guides.action_create_invoice()
        invoice.unlink()
        self.assertEqual(guides.mapped("invoice_status"), ["to_invoice", "to_invoice"])

    def test_invoice_rejects_mixed_customers_and_non_sales(self):
        mixed = self._guide("501") | self._guide("502", partner=self.other_partner)
        mixed.action_confirm()
        with self.assertRaisesRegex(UserError, "mismo cliente"):
            mixed.action_create_invoice()
        internal = self._guide("503", reason=self.reason_internal)
        internal.action_confirm()
        self.assertEqual(internal.invoice_status, "no")
        with self.assertRaises(UserError):
            internal.action_create_invoice()

    def test_cancel_sets_book_annulment_code(self):
        draft = self._guide("601")
        draft.action_cancel()
        self.assertEqual(draft.annul_code, "1")
        confirmed = self._guide("602")
        confirmed.action_confirm()
        confirmed.action_cancel()
        self.assertEqual(confirmed.annul_code, "2")
        confirmed.action_draft()
        self.assertFalse(confirmed.annul_code)

    def test_book_summary(self):
        sale = self._guide("701")
        internal = self._guide("702", reason=self.reason_internal, taxed=False)
        annulled = self._guide("703")
        (sale | internal | annulled).action_confirm()
        annulled.action_cancel()
        data = (sale | internal | annulled).get_book_data()
        self.assertEqual([line["folio"] for line in data["lines"]], ["701", "702", "703"])
        self.assertEqual(data["sales_count"], 1)
        self.assertEqual(data["sales_amount"], "12.900")
        self.assertEqual(data["annulled_guides"], 1)
        self.assertEqual(data["non_sales"], [{"code": "5", "reason": "Traslados internos", "count": 1, "amount": "11.000"}])

    def test_create_from_internal_picking(self):
        picking_type = self.env["stock.picking.type"].search([
            ("code", "=", "internal"), ("company_id", "=", self.env.company.id)], limit=1)
        picking = self.env["stock.picking"].create({
            "picking_type_id": picking_type.id,
            "location_id": picking_type.default_location_src_id.id,
            "location_dest_id": picking_type.default_location_dest_id.id,
            "move_ids": [Command.create({
                "name": self.product.name, "product_id": self.product.id, "product_uom_qty": 7,
                "product_uom": self.product.uom_id.id,
                "location_id": picking_type.default_location_src_id.id,
                "location_dest_id": picking_type.default_location_dest_id.id,
            })],
        })
        action = picking.action_create_dispatch_guide()
        guide = self.env["step.dispatch.guide"].with_context(**action["context"]).create({
            "external_folio": "801", "carrier_id": self.carrier.id,
            "driver_partner_id": self.driver.id, "truck_plate": "ABCD12",
        })
        self.assertEqual(guide.transfer_reason_id, self.reason_internal)
        self.assertEqual(guide.picking_id, picking)
        self.assertEqual(guide.line_ids.quantity, 7)
        self.assertEqual(picking.dispatch_guide_count, 1)

    def test_reports_render(self):
        guides = self._guide("901") | self._guide("902", reason=self.reason_internal)
        report = self.env["ir.actions.report"]
        html = report._render_qweb_html("step_dispatch_guide.report_dispatch_guide", guides.ids)[0].decode()
        self.assertIn("GUÍA DE DESPACHO ELECTRÓNICA", html)
        self.assertIn("Javier Reyes T25", html)
        book = report._render_qweb_html("step_dispatch_guide.report_dispatch_book", guides.ids)[0].decode()
        self.assertIn("Libro de Guías de Despacho", book)
        self.assertIn("902", book)
