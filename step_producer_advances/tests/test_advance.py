"""Native prices, receipt cohorts and reviewed 33/46 advance lifecycle."""
from datetime import date

from lxml import etree

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, tagged
from odoo.tests.common import new_test_user
from odoo.addons.step_packing_fruit_proforma.tests.common import FruitProformaCase
from odoo.addons.step_packing_operations.models.process_control import _INTERNAL


@tagged('post_install', '-at_install', 'step_producer_advances')
class TestProducerAdvances(FruitProformaCase):
    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, allowed_company_ids=(self.branch | self.root).ids))
        self.base.is_storable = True
        self.fundo = self.env['step.fundo'].with_company(self.branch).create({'name':'QA175 Fundo',
            'partner_id':self.producer.id,'company_id':self.branch.id,
            'company_ids':[Command.set((self.root | self.branch).ids)]})
        self.market = self.env['step.fruit.market'].create({'name':'QA175 Market',
            'code':'QA175','abbreviation':'Q175'})
        self.packaging = self.env['product.packaging'].create({'name':'QA175 Carton',
            'product_id':self.finished.id,'qty':1})
        self.pricelist = self.env['product.pricelist'].create({
            'name':'QA175 Producer prices','step_advance_price':True,
            'step_advance_company_ids':[Command.set((self.root | self.branch).ids)],
            'currency_id':self.root.currency_id.id})
        self.rule = self._rule(1.2)

    def _rule(self, price, **values):
        return self.env['product.pricelist.item'].create(dict({
            'pricelist_id':self.pricelist.id,'applied_on':'1_product',
            'product_tmpl_id':self.finished.product_tmpl_id.id,
            'uom_id':self.base.uom_id.id,'compute_price':'fixed','fixed_price':price},**values))

    def _receipt(self, tags, when='2026-10-29 12:00:00', kind='process',
                 actual='2026-11-10 12:00:00', has_fundo=True):
        picking = self.env['stock.picking'].with_company(self.branch).create({
            'company_id':self.branch.id,'picking_type_id':self.warehouse.in_type_id.id,
            'partner_id':self.producer.id,'location_id':self.warehouse.in_type_id.default_location_src_id.id,
            'location_dest_id':self.warehouse.in_type_id.default_location_dest_id.id,
            'step_fruit_reception_kind':kind,'fruit_fundo_id':self.fundo.id if has_fundo else False,
            'fruit_species_id':tags[:1].especie_id.id,'fruit_guide_number':'QA175-%s'%tags[:1].id})
        for tag in tags:
            self.env['step.packing.picking.tag.line'].with_company(self.branch).create({
                'picking_id':picking.id,'package_id':tag.id,'product_id':tag.step_tag_line_ids[:1].product_id.id,
                'tag_number':tag.name,'quantity':tag.step_actual_kg,'kilos':tag.step_actual_kg,
                'gross_kg':tag.step_actual_kg,'variety_id':tag.variedad_id.id})
        # Imported historical reception fixture: no inventory move is created.
        picking.flush_recordset(['state','scheduled_date','date_done'])
        self.env.cr.execute("UPDATE stock_picking SET state='done',scheduled_date=%s,date_done=%s WHERE id=%s",[when,actual,picking.id])
        picking.invalidate_recordset(['state','scheduled_date','date_done'],flush=False)
        return picking

    def _raw(self, kilos=1000, when='2026-10-29 12:00:00', species=None,
             actual='2026-11-10 12:00:00', has_fundo=True, product=None):
        species = species or self.species
        product = product or self.base
        variety = self.retained_variety if species == self.retained_species else self.variety
        tag = self.env['stock.quant.package'].with_company(self.branch).create({
            'name':'QA175 Raw %s'%when,'company_id':self.branch.id,'is_fruit_tag':True,
            'step_tag_kind':'C','step_producer_id':self.producer.id,
            'especie_id':species.id,'variedad_id':variety.id,'fruit_type':'conventional',
            'step_tag_line_ids':[Command.create({'producer_id':self.producer.id,'product_id':product.id,
                'quantity':kilos,'kilos':kilos})]})
        self.env['stock.quant'].with_company(self.branch)._update_available_quantity(
            product,self.warehouse.lot_stock_id,kilos,package_id=tag,owner_id=self.producer)
        if has_fundo:
            tag.write({'fundo_id':self.fundo.id})
        receipt = self._receipt(tag,when,actual=actual,has_fundo=has_fundo)
        tag.action_step_validate_tag()
        return tag,receipt

    def _processed(self, kilos=750, raw=None, species=None, when='2026-11-03', **tag_values):
        if raw is None:
            raw,_ = self._raw(species=species)
        production,tag,source = self._case(kilos=kilos, input_tags=raw, date=when,
            species=species,tag_values=tag_values)
        tag.action_step_validate_tag()
        return production,tag

    def _advance_wizard(self, **values):
        return self._as_accountant(self.env['step.producer.advance.prepare']).with_context(tz='America/Santiago').create(dict({
            'company_id':self.branch.id,'producer_ids':[Command.set(self.producer.ids)],
            'date_from':'2026-10-26','date_to':'2026-10-31','process_cutoff':'2026-11-05',
            'proforma_date':'2026-11-06','net_due':'2026-11-06','vat_due':'2026-12-19',
            'pricelist_id':self.pricelist.id},**values))

    def _advance(self, wizard=None):
        action = (wizard or self._advance_wizard()).action_prepare()
        self.assertEqual(action['res_model'],'purchase.order')
        if action.get('res_id'):
            return self._as_accountant(self.env['purchase.order'].browse(action['res_id']))
        return self._as_accountant(self.env['purchase.order'].search(action['domain']))

    def test_later_process_includes_only_received_cohort(self):
        order,tag = self._processed()
        order.flush_recordset(['create_date'])
        self.env.cr.execute("UPDATE step_packing_production SET create_date='2026-11-10 12:00:00' WHERE id=%s",[order.id])
        order.invalidate_recordset(['create_date'],flush=False)
        tag.pack_date='2026-11-10'
        before = self._stock_counts()
        quote = self._advance()
        self.assertEqual(quote.step_fruit_production_ids,order)
        self.assertEqual(quote.step_fruit_tag_ids,tag)
        self.assertEqual(quote.order_line.product_qty,750)
        self.assertEqual(quote.order_line.step_fruit_source_rows[0]['packing_day'],'2026-11-03')
        self.assertEqual(quote.amount_untaxed,900)
        self.assertFalse(quote.invoice_ids)
        self.assertFalse(order.purchase_bill_id)
        self.assertEqual(self._stock_counts(),before)

    def test_process_after_cutoff_is_not_included(self):
        self._processed(when='2026-11-07')
        with self.assertRaises(UserError): self._advance()

    def test_received_outside_period_is_not_included(self):
        raw,_ = self._raw(when='2026-10-20 12:00:00',actual='2026-10-27 12:00:00')
        self._processed(raw=raw)
        with self.assertRaises(UserError): self._advance()

    def test_earlier_effective_reception_selects_week_and_price(self):
        self.rule.date_end='2026-10-31 23:59:59'
        self._rule(2.1,date_start='2026-11-01 00:00:00')
        raw,_=self._raw(when='2026-11-02 12:00:00',actual='2026-10-28 12:00:00')
        self._processed(raw=raw)
        quote=self._advance()
        self.assertEqual(quote.order_line.step_fruit_source_rows[0]['receipt_day'],'2026-10-28')
        self.assertEqual(quote.order_line.price_unit,1.2)

    def test_earlier_effective_reception_before_period_is_not_included(self):
        raw,_=self._raw(actual='2026-10-20 12:00:00')
        self._processed(raw=raw)
        with self.assertRaises(UserError): self._advance()

    def test_missing_effective_date_preserves_known_scheduled_day(self):
        raw,_=self._raw(actual=None)
        self._processed(raw=raw)
        self.assertEqual(self._advance().order_line.step_fruit_source_rows[0]['receipt_day'],'2026-10-29')

    def test_historical_receipt_without_fundo_keeps_native_producer(self):
        raw,receipt=self._raw(has_fundo=False)
        self._processed(raw=raw)
        quote=self._advance()
        row=quote.order_line.step_fruit_source_rows[0]
        self.assertEqual((row['receipt_id'],row['producer_id']),(receipt.id,self.producer.id))
        self.assertFalse(row['fundo_id'])
        self.assertFalse(receipt.fruit_fundo_id)

    def test_historical_receipt_rejects_conflicting_native_producer(self):
        raw,receipt=self._raw(has_fundo=False)
        other=self.env['res.partner'].create({'name':'QA175 Otro productor','is_productor':True})
        receipt.write({'partner_id':other.id})
        self._processed(raw=raw)
        wizard=self._advance_wizard(producer_ids=[Command.clear()])
        with self.assertRaisesRegex(UserError,'mismo productor'):
            wizard.action_prepare()

    def test_legacy_output_uses_only_unique_native_product_packaging(self):
        self.rule.step_advance_packaging_id=self.packaging
        _order,tag=self._processed()
        quote=self._advance()
        self.assertEqual(quote.order_line.step_advance_packaging_id,self.packaging)
        self.assertFalse(tag.step_packaging_id)

    def test_legacy_output_does_not_guess_between_packagings(self):
        self.rule.step_advance_packaging_id=self.packaging
        self.env['product.packaging'].create({'name':'QA175 Second carton','product_id':self.finished.id,'qty':2})
        self._processed()
        with self.assertRaisesRegex(UserError,'No hay precio de anticipo'):
            self._advance()

    def test_open_process_is_not_included(self):
        order,tag = self._processed()
        order.with_context(_packing_control=_INTERNAL).write({'state':'validated'})
        with self.assertRaises(UserError): self._advance()

    def test_packed_reception_without_ot(self):
        order,tag = self._processed()
        # Create a distinct received E pallet, with no OT or manufactured stock.
        packed = self.env['stock.quant.package'].with_company(self.branch).create({
            'name':'QA175 Packed','company_id':self.branch.id,'is_fruit_tag':True,'step_tag_kind':'E',
            'step_producer_id':self.producer.id,'especie_id':self.species.id,
            'variedad_id':self.variety.id,'fruit_type':'conventional','step_packing_result':'export',
            'step_tag_line_ids':[Command.create({'producer_id':self.producer.id,'product_id':self.finished.id,
                'quantity':100,'kilos':1000,'boxes':100})]})
        self.env['stock.quant'].with_company(self.branch)._update_available_quantity(
            self.finished,self.warehouse.lot_stock_id,100,package_id=packed)
        packed.write({'fundo_id':self.fundo.id})
        packed.action_step_validate_tag()
        self._receipt(packed,when='2026-11-02 12:00:00',kind='packed',actual='2026-10-29 12:00:00')
        quote = self._advance(self._advance_wizard(process_cutoff='2026-10-31'))
        self.assertEqual(quote.step_fruit_tag_ids,packed)
        self.assertFalse(quote.step_fruit_production_ids)
        self.assertEqual(quote.order_line.product_qty,1000)

    def test_mixed_receipt_weeks_allocate_each_part_once(self):
        first,_ = self._raw(1000,'2026-10-29 12:00:00')
        second,_ = self._raw(2000,'2026-11-02 12:00:00')
        order,tag = self._processed(kilos=2250,raw=first|second)
        one = self._advance()
        self.assertEqual(one.order_line.product_qty,750)
        self.assertEqual(self._advance(),one)
        two = self._advance(self._advance_wizard(date_from='2026-11-01',date_to='2026-11-04'))
        self.assertNotEqual(one,two)
        self.assertEqual(two.order_line.product_qty,1500)
        self.assertEqual(one.amount_untaxed+two.amount_untaxed,2700)
        one._fruit_check_sources(); two._fruit_check_sources()
        self.assertFalse(tag.step_fruit_proforma_id)
        self.assertEqual(set(tag.step_advance_proforma_ids.ids),set((one|two).ids))

    def test_prices_match_market_packaging_and_original_receipt_date(self):
        self.rule.write({'date_end':'2026-10-28 23:59:59'})
        specific = self._rule(0.8,step_advance_market_id=self.market.id,step_advance_packaging_id=self.packaging.id,
            date_start='2026-10-29 00:00:00',date_end='2026-10-31 23:59:59')
        self._processed(step_advance_market_id=self.market.id,step_packaging_id=self.packaging.id)
        quote = self._advance()
        self.assertEqual(quote.order_line.price_unit,0.8)
        self.assertEqual(quote.order_line.step_advance_market_id,self.market)
        self.assertEqual(quote.order_line.step_advance_packaging_id,self.packaging)
        self.assertEqual(quote.order_line.step_fruit_source_rows[0]['price_rule_id'],specific.id)

    def test_different_receipt_prices_keep_distinct_lines(self):
        self.rule.write({'date_end':'2026-10-28 23:59:59'})
        self._rule(0.8,date_start='2026-10-29 00:00:00')
        a,_ = self._raw(1000,'2026-10-27 12:00:00')
        b,_ = self._raw(1000,'2026-10-30 12:00:00')
        self._processed(kilos=1500,raw=a|b)
        quote = self._advance()
        self.assertEqual(len(quote.order_line),2)
        self.assertEqual(set(quote.order_line.mapped('price_unit')),{1.2,0.8})
        self.assertEqual(quote.amount_untaxed,1500)

    def test_missing_price_rolls_back_without_claiming_sources(self):
        order,tag = self._processed()
        self.rule.unlink()
        before = self.env['purchase.order'].search_count([('step_advance_proforma','=',True)])
        with self.assertRaises(UserError): self._advance()
        self.assertEqual(self.env['purchase.order'].search_count([('step_advance_proforma','=',True)]),before)
        self.assertFalse(tag.step_advance_proforma_ids)

    def test_ambiguous_prices_require_explicit_resolution(self):
        self._processed(); self._rule(0.7)
        with self.assertRaises(UserError): self._advance()

    def test_selected_retention_and_native_46_conversion(self):
        self._processed(species=self.retained_species)
        quote = self._advance()
        self.assertTrue(quote.name.startswith('PA46/'))
        self.assertEqual(quote.amount_untaxed,900)
        self.assertEqual(quote.amount_total,945)
        self._approve(quote)
        bill = self._convert(quote)
        self.assertEqual(bill.l10n_latam_document_type_id.code,'46')
        self.assertFalse(bill.l10n_latam_document_number)
        self.assertEqual(bill.state,'draft')
        self.assertEqual(quote.step_advance_status,'prepared')

    def test_payment_due_dates_split_net_and_remaining_vat(self):
        self._processed(species=self.retained_species)
        quote = self._advance(); self._approve(quote); bill = self._convert(quote)
        payable = bill.line_ids.filtered(lambda line: line.account_id.account_type=='liability_payable')
        self.assertEqual(len(payable),2)
        amounts = {line.date_maturity: abs(line.amount_currency) for line in payable}
        self.assertEqual(amounts,{date(2026,11,6):900,date(2026,12,19):45})
        self.assertEqual(abs(sum(payable.mapped('balance'))),bill.amount_total)
        self.assertEqual(quote.invoice_ids,bill)
        quote.action_fruit_convert()
        self.assertEqual(quote.invoice_ids,bill)

    def test_same_payment_day_merges_native_terms(self):
        self._processed()
        quote = self._advance(self._advance_wizard(vat_due='2026-11-06'))
        self._approve(quote); bill = self._convert(quote)
        payable = bill.line_ids.filtered(lambda line: line.account_id.account_type=='liability_payable')
        self.assertEqual(len(payable),1)
        self.assertEqual(abs(payable.amount_currency),bill.amount_total)

    def test_tax_refresh_preserves_prices_and_advance_number_family(self):
        self._processed()
        quote = self._advance(); old_name=quote.name
        self.species.with_company(self.branch).write({'step_change_subject_vat':True,'step_withholding_tax_id':self.other_retention.id})
        with self.assertRaises(UserError): self._approve(quote)
        quote.action_fruit_refresh_taxes()
        self.assertTrue(quote.name.startswith('PA46/'))
        self.assertIn(old_name,quote.step_fruit_previous_references)
        self.assertEqual(quote.order_line.price_unit,1.2)
        self.assertEqual(quote.amount_tax,103.5)

    def test_monthly_preparation_blocks_active_advances(self):
        order,tag = self._processed(); self._advance()
        with self.assertRaises(UserError): self._wizard().action_prepare_bills()

    def test_monthly_claim_is_not_purchased_again_as_advance(self):
        order,tag = self._processed()
        monthly = self._prepare(order)
        with self.assertRaises(UserError): self._advance()
        self.assertEqual(tag.step_fruit_proforma_id,monthly)

    def _received_wizard(self):
        self._rule(0.8, product_tmpl_id=self.base.product_tmpl_id.id)
        return self._advance_wizard(basis='received', process_cutoff=False)

    def _commercial_product(self):
        return self.env['product.product'].with_company(self.branch).create({
            'name': 'QA198 Comercial IQF', 'default_code': 'QA198-IQF',
            'is_storable': True, 'categ_id': self.category.id,
            'uom_id': self.base.uom_id.id, 'uom_po_id': self.base.uom_id.id,
            'property_account_expense_id': self.expense.id,
        })

    def test_received_exclusion_preserves_unpriced_sources_and_the_selected_draft(self):
        included, _receipt = self._raw(species=self.retained_species)
        iqf = self._commercial_product()
        excluded, _receipt = self._raw(300, when='2026-10-30 12:00:00',
                                      species=self.retained_species, product=iqf)
        before = self._stock_counts()
        unrestricted = self._received_wizard()
        wizard = unrestricted.copy({'excluded_product_ids': [Command.set(iqf.ids)]})
        quote = self._advance(wizard)
        self.assertEqual(quote.step_advance_excluded_product_ids, iqf)
        self.assertEqual(quote.step_fruit_tag_ids, included)
        self.assertEqual(quote.order_line.product_qty, 1000)
        self.assertEqual(self._advance(wizard), quote)
        self.assertFalse(excluded.step_advance_proforma_ids)
        with self.assertRaisesRegex(UserError, 'No hay precio de anticipo'):
            self._advance(unrestricted)
        self._rule(0.5, product_tmpl_id=iqf.product_tmpl_id.id)
        second = self._advance(unrestricted) - quote
        self.assertEqual(second.step_fruit_tag_ids, excluded)
        self.assertFalse(second.step_advance_excluded_product_ids)
        self.assertEqual(quote.step_fruit_tag_ids, included)
        self._approve(quote)
        bill = self._convert(quote)
        self.assertEqual(bill.state, 'draft')
        self.assertEqual(bill.l10n_latam_document_type_id.code, '46')
        self.assertEqual(bill.invoice_line_ids.product_id, self.base)
        self.assertEqual(bill.invoice_line_ids.quantity, 1000)
        self.assertEqual(self._stock_counts(), before)

    def test_received_exclusion_does_not_return_or_change_a_mixed_existing_draft(self):
        included, _receipt = self._raw()
        iqf = self._commercial_product()
        excluded, _receipt = self._raw(300, when='2026-10-30 12:00:00', product=iqf)
        self._rule(0.5, product_tmpl_id=iqf.product_tmpl_id.id)
        wizard = self._received_wizard()
        quote = self._advance(wizard)
        wizard.excluded_product_ids = iqf
        with self.assertRaisesRegex(UserError, 'proformas que incluyen productos excluidos'):
            self._advance(wizard)
        self.assertEqual(quote.step_fruit_tag_ids, included | excluded)
        self.assertEqual(sum(quote.order_line.mapped('product_qty')), 1300)
        self.assertEqual(quote.step_fruit_state, 'draft')

    def test_processed_exclusion_can_omit_the_entire_export_cohort(self):
        _order, tag = self._processed()
        wizard = self._advance_wizard(excluded_product_ids=[Command.set(self.finished.ids)])
        with self.assertRaisesRegex(UserError, 'después de excluir'):
            self._advance(wizard)
        self.assertFalse(tag.step_advance_proforma_ids)

    def test_received_kilos_use_net_receipt_without_ot_and_prepare_native_bill(self):
        raw, receipt = self._raw(species=self.retained_species)
        before = self._stock_counts()
        wizard = self._received_wizard()
        quote = self._advance(wizard)
        self.assertEqual(quote.step_advance_basis, 'received')
        self.assertFalse(quote.step_advance_cutoff or quote.step_fruit_production_ids)
        self.assertEqual(quote.step_fruit_tag_ids, raw)
        self.assertEqual(quote.step_fruit_receipt_ids, receipt)
        self.assertEqual(quote.order_line.product_qty, 1000)
        self.assertEqual(quote.amount_untaxed, 800)
        self.assertEqual(self._advance(wizard), quote)
        self._approve(quote)
        bill = self._convert(quote)
        self.assertEqual(bill.state, 'draft')
        self.assertEqual(bill.l10n_latam_document_type_id.code, '46')
        self.assertEqual(self._stock_counts(), before)
        self._processed(raw=raw, species=self.retained_species)
        with self.assertRaisesRegex(UserError, 'No hay kilos disponibles'):
            self._advance()
        with self.assertRaisesRegex(ValidationError, 'kilos recibidos'):
            self._wizard().action_prepare_bills()

    def test_closed_ot_and_split_raw_tag_do_not_duplicate_received_fruit(self):
        raw, _receipt = self._raw()
        child = self.env['stock.quant.package'].with_company(self.branch).create({
            'name': 'QA195 split C', 'is_fruit_tag': True, 'step_tag_kind': 'C',
            'especie_id': self.species.id, 'variedad_id': self.variety.id, 'fundo_id': self.fundo.id,
            'step_producer_id': self.producer.id,
            'step_tag_line_ids': [Command.create({
                'source_package_id': raw.id, 'producer_id': self.producer.id,
                'product_id': self.base.id, 'quantity': 500, 'kilos': 500,
            })],
        })
        child.action_step_validate_tag()
        self._processed(kilos=375, raw=child)
        processed = self._advance()
        self._approve(processed)
        received = self._received_wizard()
        with self.assertRaisesRegex(UserError, 'No hay kilos disponibles'):
            self._advance(received)
        processed.button_cancel()
        self.assertEqual(self._advance(received).order_line.product_qty, 1000)

    def test_a_validated_export_tag_cannot_be_approved_again_for_another_week(self):
        first, _receipt = self._raw(1000, '2026-10-29 12:00:00')
        second, _receipt = self._raw(2000, '2026-11-02 12:00:00')
        self._processed(kilos=2250, raw=first | second)
        first_quote = self._advance()
        next_week = self._advance_wizard(date_from='2026-11-01', date_to='2026-11-04')
        second_quote = self._advance(next_week)
        self._approve(first_quote)
        with self.assertRaisesRegex(UserError, 'otra proforma'):
            self._approve(second_quote)
        with self.assertRaisesRegex(UserError, 'otra proforma'):
            self._advance(next_week)

    def test_monthly_draft_claims_original_raw_tag(self):
        raw, _receipt = self._raw()
        ot, _tag = self._processed(raw=raw)
        self._prepare(ot)
        with self.assertRaisesRegex(UserError, 'No hay kilos disponibles'):
            self._advance(self._received_wizard())

    def test_cancellation_releases_only_the_advance_allocation(self):
        order,tag = self._processed(); quote=self._advance()
        before=self._stock_counts()
        quote.button_cancel()
        again=self._advance()
        self.assertNotEqual(quote,again)
        self.assertEqual(again.order_line.product_qty,750)
        self.assertEqual(self._stock_counts(),before)

    def test_approved_sources_and_payment_dates_are_immutable(self):
        order,tag=self._processed(); quote=self._advance();self._approve(quote)
        with self.assertRaises(UserError):quote.write({'step_advance_vat_due':'2027-01-01'})
        with self.assertRaises(UserError):tag.write({'step_advance_market_id':self.market.id})
        with self.assertRaises(UserError):quote.copy()

    def test_ordinary_purchase_cannot_forge_advance_flag(self):
        with self.assertRaises(UserError):
            self.env['purchase.order'].create(dict(self._ordinary_values(),step_advance_proforma=True))

    def test_shared_prices_use_native_models_and_company_rules(self):
        self.assertEqual(self.pricelist._name,'product.pricelist')
        self.assertFalse(self.pricelist.company_id)
        self.assertEqual(self.rule._name,'product.pricelist.item')
        foreign=self.env['res.company'].create({'name':'QA175 Foreign'})
        user=new_test_user(self.env,login='qa175-limited',groups='account.group_account_user',company_id=self.branch.id,
            company_ids=[Command.set(self.branch.ids)])
        with self.assertRaises(ValidationError):
            self.pricelist.with_user(user).with_context(allowed_company_ids=self.branch.ids).write({
                'step_advance_company_ids':[Command.set(foreign.ids)]})

    def test_ordinary_tariff_requirement_and_native_editor_are_preserved(self):
        ordinary=self.env['product.pricelist'].create({'name':'QA175 Ordinary','company_id':self.branch.id})
        with self.assertRaises(ValidationError),self.env.cr.savepoint():
            self.env['product.pricelist.item'].create({'pricelist_id':ordinary.id,'uom_id':self.base.uom_id.id,
                'product_tmpl_id':self.base.product_tmpl_id.id,'fixed_price':3})
        rule=self.env['product.pricelist.item'].create({'pricelist_id':ordinary.id,'uom_id':self.base.uom_id.id,
            'labor_id':self.base.product_tmpl_id.id,'product_tmpl_id':self.base.product_tmpl_id.id,'fixed_price':3})
        self._as_accountant(rule).write({'fixed_price':4})
        self.assertEqual(rule.fixed_price,4)

    def test_accountant_can_edit_only_advance_prices_without_native_product_role(self):
        user=new_test_user(self.env,login='qa175-price-accountant',groups='account.group_account_user',company_id=self.branch.id,
            company_ids=[Command.set(self.branch.ids)])
        scoped=self.pricelist.with_user(user).with_context(allowed_company_ids=self.branch.ids)
        scoped.write({'name':'QA175 Account edited'})
        ordinary=self.env['product.pricelist'].create({'name':'QA175 Ordinary guarded','company_id':self.branch.id})
        with self.assertRaises(AccessError):ordinary.with_user(user).with_context(allowed_company_ids=self.branch.ids).write({'name':'not allowed'})

    def test_html_annex_reconciles_with_summary_and_retention(self):
        self._processed(species=self.retained_species)
        quote=self._advance()
        report=self.env['report.step_producer_advances.report_advance']
        data=report._advance_data(quote)
        self.assertEqual(data['received'],1000)
        self.assertEqual(data['exported'],750)
        self.assertEqual(data['ratio'],0.75)
        self.assertEqual(sum(row['print_amount'] for row in data['rows']),quote.amount_untaxed)
        html,_=self.env['ir.actions.report']._render_qweb_html('step_producer_advances.report_advance',quote.ids)
        for token in (b'ANEXO DETALLE PROFORMA',b'Fechas de pago',b'PA46/',b'QA175'):
            self.assertIn(token,html)

    def test_native_forms_and_menu_show_requested_fields(self):
        business=self.env(user=self.operator,su=False,context=dict(self.env.context,allowed_company_ids=self.branch.ids))
        menu=business.ref('step_producer_advances.menu_producer_advances')
        self.assertEqual(menu.parent_id,business.ref('step_producers.menu_step_producers_root'))
        self.assertGreater(menu.sequence,business.ref('step_producers.menu_step_producers_fruit_group').sequence)
        self.assertLess(menu.sequence,business.ref('step_producers.menu_step_producers_settlement_group').sequence)
        with Form(business['step.producer.advance.prepare'],view='step_producer_advances.advance_prepare_form') as form:
            form.pricelist_id=self.pricelist
            form.net_due=date(2026,11,6);form.vat_due=date(2026,12,19)
        view=business['product.pricelist'].get_view(view_id=business.ref('step_producer_advances.advance_pricelist_form').id,view_type='form')['arch']
        tree=etree.fromstring(view)
        self.assertTrue(tree.xpath("//field[@name='step_advance_company_ids']"))
        for excluded in ('group_type','country_group_ids','partner_ids','escalonado','cost_ids','movilizacion'):
            self.assertFalse(tree.xpath("//field[@name=%r]"%excluded))

    def test_local_reception_boundary_and_cross_month_period(self):
        raw,_=self._raw(when='2026-11-01 02:00:00')
        self._processed(raw=raw)
        quote=self._advance(self._advance_wizard(date_from='2026-10-31',date_to='2026-11-01'))
        self.assertEqual(quote.order_line.product_qty,750)
        self.assertEqual(quote.order_line.step_fruit_source_rows[0]['receipt_day'],'2026-10-31')

    def test_invalid_cutoff_and_missing_payment_dates_are_rejected(self):
        self._processed()
        with self.assertRaises(ValidationError):self._advance(self._advance_wizard(process_cutoff='2026-10-30'))

