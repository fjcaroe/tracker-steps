"""Rollback-only native weekly advances, using the established monthly fixtures."""
from pathlib import Path

from lxml import etree

from fruit_proforma_checks import verify_copy_cycle


def verify_ui(business):
    ref = business.ref
    advance = ref('step_producer_advances.menu_producer_advances')
    visible = business['ir.ui.menu']._visible_menu_ids()
    assert advance.id in visible
    assert ref('step_producers.menu_step_producers_fruit_group').sequence < advance.sequence < ref('step_producers.menu_step_producers_settlement_group').sequence
    price = etree.fromstring(business['product.pricelist'].get_view(
        view_id=ref('step_producer_advances.advance_pricelist_form').id, view_type='form')['arch'])
    for name in ('step_advance_company_ids', 'currency_id', 'date_init', 'date_end', 'especie_id', 'item_ids'):
        assert price.xpath('//field[@name=%r]' % name)
    for name in ('group_type', 'country_group_ids', 'partner_ids', 'escalonado', 'cost_ids'):
        assert not price.xpath('//field[@name=%r]' % name)
    quote = etree.fromstring(business['purchase.order'].get_view(
        view_id=ref('step_producer_advances.advance_proforma_form').id, view_type='form')['arch'])
    for name in ('step_advance_pricelist_id', 'step_advance_net_due', 'step_advance_vat_due', 'step_advance_status'):
        assert quote.xpath('//field[@name=%r]' % name)
    wizard = etree.fromstring(business['step.producer.advance.prepare'].get_view(
        view_id=ref('step_producer_advances.advance_prepare_form').id, view_type='form')['arch'])
    for name in ('producer_ids', 'species_ids', 'date_from', 'date_to', 'process_cutoff', 'net_due', 'vat_due'):
        assert wizard.xpath('//field[@name=%r]' % name)
    tag = etree.fromstring(business['stock.quant.package'].get_view(
        view_id=ref('step_inventory_packing.view_quant_package_form_steps_fruit').id, view_type='form')['arch'])
    assert tag.xpath('//field[@name="step_advance_proforma_ids"]')
    assert tag.xpath('//field[@name="step_advance_market_id"]')
    return {'menus': True, 'native_pricelist': True, 'effective_forms': True, 'tag_proforma_links': True}


def verify_advances(env, output):
    assert env.cr.dbname.startswith('MANAGEMENT_QA_')
    from odoo import Command
    from odoo.addons.step_packing_operations.models.process_control import _INTERNAL
    from odoo.addons.step_packing_fruit_proforma.purchase import _controlled
    monthly, case = verify_copy_cycle(env, output, return_fixture=True)
    admin, business = case['admin'].with_company(case['branch']), case['business']
    branch, producer, finished = case['branch'], case['producer'], case['finished']
    fundo = admin['step.fundo'].with_company(branch).create({'name':'QA175 smoke fundo','company_id':branch.id,
        'partner_id':producer.id,'company_ids':[Command.set((case['holding'] | branch).ids)]})
    market = admin['step.fruit.market'].create({'name':'QA175 smoke market','code':'QA175','abbreviation':'QA175'})
    packaging = admin['product.packaging'].create({'name':'QA175 smoke carton','product_id':finished.id,'qty':1})
    prices = business['product.pricelist'].create({'name':'QA175 smoke producer prices','step_advance_price':True,
        'step_advance_company_ids':[Command.set(branch.ids)],'currency_id':branch.currency_id.id})
    business['product.pricelist.item'].create({'pricelist_id':prices.id,'product_tmpl_id':finished.product_tmpl_id.id,
        'applied_on':'1_product','compute_price':'fixed','fixed_price':1.2,
        'uom_id':admin.ref('uom.product_uom_kgm').id,'step_advance_market_id':market.id,'step_advance_packaging_id':packaging.id})

    def tag(kind, code, kilos, product):
        species, variety = case['species_by_code'][code]
        record = admin['stock.quant.package'].with_company(branch).create({
            'name':'QA175 smoke %s %s'%(kind,code),'company_id':branch.id,'is_fruit_tag':True,
            'step_tag_kind':kind,'step_packing_result':'export' if kind=='E' else False,
            'step_producer_id':producer.id,'especie_id':species.id,'variedad_id':variety.id,
            'fruit_type':'conventional','step_advance_market_id':market.id,
            'step_packaging_id':packaging.id if kind=='E' else False,
            'step_tag_line_ids':[Command.create({'producer_id':producer.id,'product_id':product.id,
                'quantity':kilos if kind=='C' else kilos/10,'kilos':kilos})]})
        return record

    def receipt(record, kind):
        detail=record.step_tag_line_ids
        admin['stock.quant'].with_company(branch)._update_available_quantity(
            detail.product_id,case['warehouse'].lot_stock_id,detail.quantity,package_id=record,
            owner_id=producer if kind=='process' else None)
        record.write({'fundo_id':fundo.id})
        picking = admin['stock.picking'].with_company(branch).create({
            'company_id':branch.id,'picking_type_id':case['warehouse'].in_type_id.id,
            'partner_id':producer.id,'location_id':case['warehouse'].in_type_id.default_location_src_id.id,
            'location_dest_id':case['warehouse'].in_type_id.default_location_dest_id.id,
            'step_fruit_reception_kind':kind,'fruit_fundo_id':fundo.id,'fruit_species_id':record.especie_id.id,
            'fruit_guide_number':'QA175 smoke guide '+kind})
        admin['step.packing.picking.tag.line'].with_company(branch).create({'picking_id':picking.id,'package_id':record.id,
            'product_id':record.step_tag_line_ids.product_id.id,'tag_number':record.name,
            'quantity':record.step_tag_line_ids.quantity,'kilos':record.step_actual_kg,
            'gross_kg':record.step_actual_kg,'variety_id':record.variedad_id.id})
        picking.flush_recordset(['state','scheduled_date','date_done'])
        admin.cr.execute("UPDATE stock_picking SET state='done',scheduled_date='2026-10-29 12:00:00',date_done='2026-11-06 12:00:00' WHERE id=%s",[picking.id])
        picking.invalidate_recordset(['state','scheduled_date','date_done'],flush=False)
        record.action_step_validate_tag()

    packed = tag('E','33',1000,finished);receipt(packed,'packed')
    raw = tag('C','46',1000,case['base']);receipt(raw,'process')
    result = tag('E','46',750,finished)
    production = admin['step.packing.production'].with_company(branch).create({
        'company_id':branch.id,'date':'2026-11-03','fruit_grower_id':producer.id,
        'fruit_species_id':result.especie_id.id,'fruit_variety_id':result.variedad_id.id,
        'step_packing_input_tag_ids':[Command.set(raw.ids)],'step_packing_output_tag_ids':[Command.set(result.ids)]})
    production.with_context(_packing_control=_INTERNAL).write({'state':'closed'})
    result.action_step_validate_tag()
    counts = lambda: tuple(business[model].search_count([('company_id','=',branch.id)])
        for model in ('stock.picking','stock.move','stock.quant','stock.valuation.layer'))
    stock = counts()
    account_before = business['account.move'].search([('company_id','=',branch.id)])
    wizard = business['step.producer.advance.prepare'].with_context(tz='America/Santiago').create({
        'company_id':branch.id,'producer_ids':[Command.set(producer.ids)],'pricelist_id':prices.id,
        'date_from':'2026-10-26','date_to':'2026-10-31','process_cutoff':'2026-11-05',
        'proforma_date':'2026-11-06','net_due':'2026-11-06','vat_due':'2026-12-19'})
    action = wizard.action_prepare()
    quotes = business['purchase.order'].search(action['domain'])
    assert len(quotes)==2 and set(quotes.mapped('step_fruit_dte_code'))=={'33','46'}
    assert all(not quote.invoice_ids and quote.step_fruit_state=='draft' for quote in quotes)
    assert business['account.move'].search([('company_id','=',branch.id)])==account_before
    assert counts()==stock
    html, _ = business['ir.actions.report']._render_qweb_html('step_producer_advances.report_advance',quotes.ids)
    assert b'ANEXO DETALLE PROFORMA' in html and b'Fechas de pago' in html
    pdf, kind = business['ir.actions.report']._render_qweb_pdf('step_producer_advances.report_advance',quotes.ids)
    assert kind=='pdf' and pdf.startswith(b'%PDF') and len(pdf)>10000
    (Path(output)/'t175-smoke-advances.pdf').write_bytes(pdf)
    retained = quotes.filtered(lambda quote:quote.step_fruit_dte_code=='46')
    assert retained.amount_untaxed==900 and retained.amount_total==945
    line = retained.order_line
    class LayoutChecked(Exception): pass
    try:
        with admin.cr.savepoint():
            row = line.step_fruit_source_rows[0]
            large = [dict(row,tag_name='QA175-%04d'%number,quantity=row['quantity']/1000,
                received_kg=row['received_kg']/1000,amount=row['amount']/1000,
                source_amount=row['source_amount']/1000) for number in range(1,1001)]
            _controlled(line).write({'step_fruit_source_rows':large})
            pdf,kind = business['ir.actions.report']._render_qweb_pdf('step_producer_advances.report_advance',retained.ids)
            assert kind=='pdf' and pdf.startswith(b'%PDF') and len(pdf)>20000
            (Path(output)/'t175-large-advance.pdf').write_bytes(pdf)
            raise LayoutChecked()
    except LayoutChecked:
        pass
    quotes.write({'step_fruit_approval_reference':'QA175 native review'})
    quotes.action_fruit_approve()
    ordinary=quotes-retained
    ordinary.write({'step_fruit_supplier_invoice_received':True,'step_fruit_supplier_document_number':'17533'})
    quotes.action_fruit_convert()
    bills=quotes.invoice_ids
    assert len(bills)==2 and set(bills.mapped('state'))=={'draft'}
    assert set(bills.l10n_latam_document_type_id.mapped('code'))=={'33','46'}
    assert not retained.invoice_ids.l10n_latam_document_number
    for quote in quotes:
        terms=quote.invoice_ids.line_ids.filtered(lambda row:row.account_id.account_type=='liability_payable')
        by_date={str(row.date_maturity):abs(row.amount_currency) for row in terms}
        assert by_date=={'2026-11-06':quote.amount_untaxed,'2026-12-19':quote.amount_tax}
    quotes.action_fruit_convert();wizard.action_prepare()
    assert quotes.invoice_ids==bills and counts()==stock
    assert not production.purchase_bill_id
    return {'monthly_regression':monthly,'documents':['33','46'],'late_process':True,
        'packed_reception':True,'native_invoice_drafts':True,'two_payment_dates':True,
        'idempotent':True,'stock_preserved':True,'no_official_folio':True,'large_annex_rows':1000}
