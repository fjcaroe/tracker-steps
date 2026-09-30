from datetime import date

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestExportOperations(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.receiver = cls.env["res.partner"].create({
            "name": "Receiver T35", "step_export_receiver": True,
            "country_id": cls.env.ref("base.us").id,
            "l10n_cl_sii_taxpayer_type": "4",
        })
        cls.producer = cls.env["res.partner"].create({
            "name": "Producer T35", "is_productor": True,
            "country_id": cls.env.ref("base.cl").id,
            "vat": "CL11111111-1", "l10n_cl_sii_taxpayer_type": "1",
        })
        cls.season = cls.env["step.temporada"].create({"name": "Season T35 ops"})
        cls.species = cls.env["step.especie"].create({
            "name": "Cherry T35 ops", "type_especie": "frutal", "group_especie": "seco",
        })
        cls.product = cls.env["product.product"].create({
            "name": "Cherry box T35", "grupo_labor": "pack", "is_fruta": True,
            "step_export_enabled": True,
        })
        cls.package_type = cls.env["stock.package.type"].create({"name": "Pallet T35 ops"})
        cls.program = cls.env["step.export.sales.program"].create({
            "name": "Cherry programme", "partner_id": cls.receiver.id,
            "season_id": cls.season.id, "species_id": cls.species.id,
            "product_id": cls.product.id, "package_type_id": cls.package_type.id,
            "date_start": date(2026, 11, 2), "date_end": date(2026, 11, 9),
            "pallets_per_container": 1, "boxes_per_pallet": 10, "kg_per_box": 5,
            "rate_to_usd": 1,
            "line_ids": [(0, 0, {"week_start": date(2026, 11, 2), "container_qty": 1,
                                  "price_per_kg": 10}),
                         (0, 0, {"week_start": date(2026, 11, 9), "container_qty": 1,
                                  "price_per_kg": 12})],
        })
        cls.program.action_validate()
        cls.program.action_activate()
        cls.shipment = cls.env["step.export.export"].create({
            "name": "T35 test shipment", "sales_program_id": cls.program.id,
            "date": date(2026, 11, 3),
            "line_ids": [(0, 0, {"product_id": cls.product.id,
                                  "pallet_qty": 1, "boxes_per_pallet": 10, "kg_per_box": 5})],
        })

    def test_producer_rate_uses_receiver_company(self):
        other_company = self.env["res.company"].create({"name": "Otra empresa T35"})
        wrong_rate = self.env["step.export.grower.rate"].create({
            "name": "Tarifa otra empresa T35", "producer_id": self.producer.id,
            "company_id": other_company.id, "season_id": self.season.id,
            "species_id": self.species.id, "rate_value": 9,
        })
        expected_rate = self.env["step.export.grower.rate"].create({
            "name": "Tarifa empresa actual T35", "producer_id": self.producer.id,
            "company_id": self.env.company.id, "season_id": self.season.id,
            "species_id": self.species.id, "rate_value": 1,
        })
        receiver = self.env["step.export.receiver.settlement"].create({
            "receiver_id": self.receiver.id, "sales_program_id": self.program.id,
            "date": date(2026, 11, 20), "rate_to_usd": 1,
        })
        producer = self.env["step.export.producer.settlement"].create({
            "receiver_settlement_id": receiver.id, "producer_id": self.producer.id,
        })
        self.assertNotEqual(producer.rate_id, wrong_rate)
        self.assertEqual(producer.rate_id, expected_rate)

    def test_shipment_validation_and_document_gate(self):
        self.assertEqual(self.shipment.kg_qty, 50)
        self.shipment.action_validate_shipment()
        self.assertEqual(self.shipment.receiver_id, self.receiver)
        with self.assertRaises(UserError):
            self.shipment.action_dispatch()

    def test_company_accounting_defaults_for_new_producer_rate(self):
        company = self.env.company
        account = self.env["account.account"].search([
            ("company_ids", "in", company.id), ("account_type", "=", "expense")], limit=1)
        tax = self.env["account.tax"].search([
            ("company_id", "=", company.id), ("type_tax_use", "=", "purchase"),
            ("amount", "=", 19)], limit=1)
        journal = self.env["account.journal"].search([
            ("company_id", "=", company.id), ("type", "=", "purchase")], limit=1)
        self.assertTrue(account and tax and journal)
        company.write({
            "step_export_purchase_account_id": account.id,
            "step_export_purchase_tax_id": tax.id,
            "step_export_purchase_journal_id": journal.id,
        })
        rate = self.env["step.export.grower.rate"].create({
            "name": "Tarifa configurada T35", "company_id": company.id,
            "producer_id": self.producer.id, "season_id": self.season.id,
            "species_id": self.species.id, "rate_value": 2,
        })
        self.assertEqual(rate.expense_account_id, account)
        self.assertEqual(rate.purchase_tax_ids, tax)

    def test_claim_changes_receiver_fob_and_requires_posted_invoice(self):
        tag = self.env["stock.quant.package"].create({
            "name": "T35-TAG-CLAIM", "is_fruit_tag": True, "owner_id": self.producer.id,
        })
        self.shipment.tag_ids = tag
        claim = self.env["step.export.customer.claim"].create({
            "name": "Damage at destination", "receiver_id": self.receiver.id,
            "claimed_amount_usd": 20, "accepted_amount_usd": 20,
            "shipment_ids": [(4, self.shipment.id)], "tag_ids": [(4, tag.id)],
        })
        claim.action_accept()
        self.assertIn(claim, self.shipment.claim_ids)
        self.assertIn(claim, tag.step_export_claim_ids)
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice", "partner_id": self.receiver.id,
            "currency_id": self.env.ref("base.USD").id,
            "step_export_shipment_id": self.shipment.id,
        })
        settlement = self.env["step.export.receiver.settlement"].create({
            "receiver_id": self.receiver.id, "sales_program_id": self.program.id,
            "rate_to_usd": 1.25,
            "line_ids": [(0, 0, {"shipment_id": self.shipment.id, "invoice_id": invoice.id,
                                  "sales_amount": 1000, "expenses_usd": 100,
                                  "commission_rate": 0.1})],
        })
        line = settlement.line_ids
        self.assertAlmostEqual(line.sales_usd, 1250)
        self.assertAlmostEqual(line.claim_usd, 20)
        self.assertAlmostEqual(line.commission_usd, 125)
        self.assertAlmostEqual(line.fob_usd, 1005)
        with self.assertRaises(ValidationError):
            settlement.action_validate()

    def test_packaging_materials_and_five_week_forecast(self):
        material = self.env["product.product"].create({
            "name": "Carton T35", "grupo_labor": "pack", "standard_price": 2,
        })
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": self.product.product_tmpl_id.id,
            "product_qty": 1, "step_export_fruit": True,
            "bom_line_ids": [(0, 0, {"product_id": material.id, "product_qty": 2,
                                       "step_export_qty_per_pallet": 1})],
        })
        concept = self.env["step.export.payment.concept"].create({
            "name": "Packing labour T35", "standard_cost_per_kg": 0.5,
        })
        packing = self.env["step.export.packaging.program"].create({
            "name": "Packing T35", "sales_program_id": self.program.id,
            "bom_id": bom.id, "cost_line_ids": [(0, 0, {"concept_id": concept.id})],
        })
        packing.action_validate()
        packing.action_value()
        self.assertEqual(packing.material_line_ids.standard_consumption, 42)
        self.assertEqual(packing.cost_line_ids.amount_usd, 50)
        forecast = self.env["step.export.forecast"].create({
            "name": "Forecast T35", "season_id": self.season.id,
            "cutoff_week": date(2026, 10, 26),
        })
        forecast.action_generate()
        self.assertEqual(len(forecast.line_ids), 6)
        self.assertEqual(forecast.line_ids[0].program_kg, 50)
        self.assertEqual(forecast.remaining_kg, 100)

    def test_receiver_and_producer_accounting(self):
        company = self.env.company
        account_domain = [("account_type", "=", "income")]
        if "company_ids" in self.env["account.account"]._fields:
            account_domain.append(("company_ids", "in", company.id))
        else:
            account_domain.append(("company_id", "=", company.id))
        income_account = self.env["account.account"].search(account_domain, limit=1)
        purchase_domain = [("account_type", "=", "expense")]
        purchase_domain.extend(account_domain[1:])
        expense_account = self.env["account.account"].search(purchase_domain, limit=1)
        sale_journal = self.env["account.journal"].search([
            ("company_id", "=", company.id), ("type", "=", "sale")], limit=1)
        purchase_tax = self.env["account.tax"].search([
            ("company_id", "=", company.id), ("type_tax_use", "=", "purchase"),
            ("amount", "=", 19)], limit=1)
        self.assertTrue(income_account and expense_account and sale_journal and purchase_tax)
        purchase_journal = self.env["account.journal"].create({
            "name": "Compras fruta T35", "code": "PT35", "type": "purchase",
            "company_id": company.id,
        })
        self.env["step.export.grower.rate"].create({
            "name": "Rate T35", "producer_id": self.producer.id,
            "season_id": self.season.id, "species_id": self.species.id,
            "rate_type": "usd_kg", "rate_value": 1,
            "expense_account_id": expense_account.id,
            "purchase_tax_ids": [(4, purchase_tax.id)],
        })
        self.product.write({"weight": 5, "is_storable": True})
        tag = self.env["stock.quant.package"].create({
            "name": "T35-TAG-ACCOUNTING", "is_fruit_tag": True,
            "owner_id": self.producer.id, "step_export_season_id": self.season.id,
            "especie_id": self.species.id, "box_count": 10,
        })
        location = self.env.ref("step_inventory_fruit_tag.stock_location_bodega_fruta")
        self.env["stock.quant"]._update_available_quantity(
            self.product, location, 10, package_id=tag, owner_id=self.producer)
        self.assertAlmostEqual(tag.kilos_total, 50)
        self.shipment.write({
            "state": "invoiced", "tag_ids": [(4, tag.id)], "ivv_folio": "IVV-T35-1",
        })
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice", "partner_id": self.receiver.id,
            "journal_id": sale_journal.id, "currency_id": self.env.ref("base.USD").id,
            "invoice_date": date(2026, 11, 3), "step_export_shipment_id": self.shipment.id,
            "invoice_line_ids": [(0, 0, {
                "name": "Fruit T35", "quantity": 1, "price_unit": 100,
                "account_id": income_account.id, "tax_ids": [(5, 0, 0)],
            })],
        })
        if "l10n_latam_document_type_id" in invoice._fields and company.country_id.code == "CL":
            export_invoice_type = self.env["l10n_latam.document.type"].search([
                ("code", "=", "110")], limit=1)
            self.assertTrue(export_invoice_type)
            invoice.l10n_latam_document_type_id = export_invoice_type
        invoice.action_post()
        settlement = self.env["step.export.receiver.settlement"].create({
            "receiver_id": self.receiver.id, "sales_program_id": self.program.id,
            "date": date(2026, 11, 20), "rate_to_usd": 1,
            "line_ids": [(0, 0, {"shipment_id": self.shipment.id, "invoice_id": invoice.id,
                                  "sales_amount": 150, "expenses_usd": 0,
                                  "external_adjustment_folio": "DTE-111-T35"})],
        })
        settlement.action_prepare_grade_lines()
        self.assertEqual(len(settlement.line_ids.grade_line_ids), 1)
        self.assertAlmostEqual(settlement.line_ids.grade_line_ids.fob_usd, 150)
        self.assertAlmostEqual(settlement.total_difference_usd, 50)
        settlement.action_validate()
        self.assertEqual(self.shipment.state, "settled")
        self.assertEqual(len(settlement.producer_settlement_ids), 1)
        settlement.action_account()
        self.assertEqual(settlement.adjustment_move_ids.state, "posted")
        self.assertEqual(settlement.adjustment_move_ids.move_type, "entry")
        receivable_line = settlement.adjustment_move_ids.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable")
        self.assertAlmostEqual(receivable_line.amount_currency, 50)
        producer_settlement = settlement.producer_settlement_ids
        producer_settlement.payout_mode = "rate"  # conserva la fórmula histórica de este caso
        self.assertAlmostEqual(producer_settlement.net_usd, 50)
        initial_bill = self.env["account.move"].create({
            "move_type": "in_invoice", "company_id": company.id,
            "partner_id": self.producer.id, "journal_id": purchase_journal.id,
            "currency_id": company.currency_id.id,
            "invoice_date": date(2026, 11, 3), "ref": "33-T35-INITIAL",
            "invoice_line_ids": [(0, 0, {
                "name": "Initial fruit purchase", "quantity": 1,
                "price_unit": self.env.ref("base.USD")._convert(
                    20, company.currency_id, company, date(2026, 11, 3)),
                "account_id": expense_account.id,
                "tax_ids": [(6, 0, purchase_tax.ids)],
            })],
        })
        if "l10n_latam_document_type_id" in initial_bill._fields:
            initial_bill.l10n_latam_document_type_id = self.env["l10n_latam.document.type"].search([
                ("code", "=", "33")], limit=1)
        initial_bill.action_post()
        producer_settlement.initial_bill_ids = initial_bill
        self.assertAlmostEqual(producer_settlement.adjustment_usd, 30, places=2)
        producer_settlement.initial_bills_reviewed = True
        producer_settlement.purchase_journal_id = purchase_journal
        producer_settlement.supplier_document_code = "56"
        producer_settlement.supplier_invoice_folio = "56-T35-ADJUSTMENT"
        producer_settlement.action_validate()
        producer_settlement.action_account()
        self.assertEqual(producer_settlement.bill_id.state, "posted")
        self.assertEqual(producer_settlement.state, "accounted")
        self.assertTrue(producer_settlement.delivery_date)
        producer_settlement.action_close()
        self.assertEqual(producer_settlement.state, "closed")
        self.assertTrue(producer_settlement.closed_date)
        report = self.env.ref("step_export.action_report_producer_settlement")
        html, _ = report._render_qweb_html(
            report.report_name, [producer_settlement.id])
        self.assertIn(b"Liquidaci", html)
        self.assertIn(b"T35-TAG-ACCOUNTING", html)
        self.assertAlmostEqual(producer_settlement.bill_id.amount_untaxed,
                               self.env.ref("base.USD")._convert(
                                   30, company.currency_id, company, date(2026, 11, 20)), places=2)

        credit_tag = self.env["stock.quant.package"].create({
            "name": "T35-TAG-CREDIT", "is_fruit_tag": True,
            "owner_id": self.producer.id, "step_export_season_id": self.season.id,
            "especie_id": self.species.id, "box_count": 10,
        })
        self.env["stock.quant"]._update_available_quantity(
            self.product, location, 10, package_id=credit_tag, owner_id=self.producer)
        credit_shipment = self.env["step.export.export"].create({
            "name": "T35 credit adjustment", "sales_program_id": self.program.id,
            "date": date(2026, 11, 4),
            "ivv_folio": "IVV-T35-2", "tag_ids": [(4, credit_tag.id)],
            "line_ids": [(0, 0, {"product_id": self.product.id,
                                  "pallet_qty": 1, "boxes_per_pallet": 10, "kg_per_box": 5})],
        })
        credit_shipment.state = "invoiced"
        credit_invoice = self.env["account.move"].create({
            "move_type": "out_invoice", "partner_id": self.receiver.id,
            "journal_id": sale_journal.id, "currency_id": self.env.ref("base.USD").id,
            "invoice_date": date(2026, 11, 4), "step_export_shipment_id": credit_shipment.id,
            "invoice_line_ids": [(0, 0, {
                "name": "Fruit T35 credit", "quantity": 1, "price_unit": 100,
                "account_id": income_account.id, "tax_ids": [(5, 0, 0)],
            })],
        })
        if "l10n_latam_document_type_id" in credit_invoice._fields and company.country_id.code == "CL":
            credit_invoice.l10n_latam_document_type_id = self.env["l10n_latam.document.type"].search([
                ("code", "=", "110")], limit=1)
        credit_invoice.action_post()
        credit_settlement = self.env["step.export.receiver.settlement"].create({
            "receiver_id": self.receiver.id, "sales_program_id": self.program.id,
            "date": date(2026, 11, 21), "rate_to_usd": 1,
            "line_ids": [(0, 0, {"shipment_id": credit_shipment.id,
                                  "invoice_id": credit_invoice.id, "sales_amount": 80})],
        })
        self.assertAlmostEqual(credit_settlement.total_difference_usd, -20)
        credit_settlement.action_validate()
        credit_settlement.action_account()
        self.assertEqual(credit_settlement.adjustment_move_ids.move_type, "out_refund")
        self.assertEqual(credit_settlement.adjustment_move_ids.l10n_latam_document_type_id.code, "112")
