"""Exercise the unchanged monthly customer documents inside a disposable copy.

The only setup writes are the newly introduced species-policy fields.  The
caller must roll back the complete transaction, including those setup writes.
"""
import hashlib
import json

from native_business_profile import scoped_business_environment


def _digest(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()


def _read(records, names):
    records = records.sorted('id')
    records.invalidate_recordset(names)
    return records.read(names)


def _stock_fingerprint(env, company):
    fields = {
        'stock.quant': ['product_id', 'location_id', 'lot_id', 'package_id', 'owner_id',
                        'quantity', 'reserved_quantity', 'company_id'],
        'stock.move': ['product_id', 'product_uom_qty', 'product_uom', 'quantity', 'state',
                       'location_id', 'location_dest_id', 'picking_id', 'company_id'],
        'stock.move.line': ['product_id', 'product_uom_id', 'quantity', 'lot_id', 'package_id',
                            'result_package_id', 'owner_id', 'state', 'location_id',
                            'location_dest_id', 'picking_id', 'company_id'],
        'stock.valuation.layer': ['product_id', 'stock_move_id', 'quantity', 'value',
                                  'remaining_qty', 'remaining_value', 'company_id'],
    }
    return {model: _digest(_read(env[model].search([('company_id', '=', company.id)]), names))
            for model, names in fields.items()}


def verify_case(env, plan):
    assert env.cr.dbname.startswith('MANAGEMENT_QA_CERRO_'), 'Customer case is copy-only'
    company = env['res.company'].browse(plan['company_id']).exists()
    assert len(company) == 1
    business = scoped_business_environment(env, company=company)
    assert not business.su and business.companies == company
    contract = business['step.producer.purchase.contract'].browse(plan['contract_id']).exists()
    contract.check_access('read')
    orders = business['step.packing.production'].search([
        ('company_id', '=', company.id), ('fruit_grower_id', '=', contract.partner_id.id),
        ('date', '>=', plan['date_start']), ('date', '<=', plan['date_end']),
        ('state', 'in', ['closed', 'costed', 'accounted'])])
    assert orders and set(orders.ids) == set(plan['order_ids'])
    legacy = business['account.move'].browse(plan['legacy_move_ids']).exists()
    assert legacy and set(orders.purchase_bill_id.ids) == set(legacy.ids)
    assert all(move.state == 'draft' and not move.posted_before
               and move.company_id == company and not move.step_fruit_proforma_id for move in legacy)
    tags = orders.step_packing_output_tag_ids.filtered(lambda tag: tag.step_packing_result == 'export')
    assert tags and not tags.step_fruit_proforma_id
    species = business['step.especie'].browse(plan['species_id']).exists()
    retention = business['account.tax'].browse(plan['withholding_tax_id']).exists()
    assert len(species) == 1 and len(retention) == 1
    products = tags.step_tag_line_ids.product_id | contract.product_line_ids.product_id
    categories = products.categ_id
    taxes = products.supplier_taxes_id | legacy.invoice_line_ids.tax_ids | retention
    taxes |= taxes.flatten_taxes_hierarchy()
    repartitions = taxes.invoice_repartition_line_ids | taxes.refund_repartition_line_ids
    accounts = contract.product_line_ids.debit_account_id | products.with_company(company).property_account_expense_id
    accounts |= categories.with_company(company).property_account_expense_categ_id
    accounts |= legacy.line_ids.account_id
    master_sets = [
        (contract, ['name', 'partner_id', 'company_id', 'currency_id', 'state', 'date_start', 'date_end']),
        (contract.product_line_ids, ['product_id', 'species_id', 'variety_id', 'category_id',
                                    'caliber_id', 'quantity', 'uom_id', 'price_unit', 'debit_account_id']),
        (products.with_company(company), ['name', 'default_code', 'uom_id', 'uom_po_id',
                                         'supplier_taxes_id', 'property_account_expense_id', 'categ_id', 'standard_price']),
        (categories.with_company(company), ['name', 'property_account_expense_categ_id']),
        (taxes, ['name', 'amount', 'amount_type', 'type_tax_use', 'company_id', 'active',
                  'price_include', 'children_tax_ids', 'invoice_repartition_line_ids', 'refund_repartition_line_ids']),
        (repartitions, ['factor_percent', 'account_id', 'tag_ids', 'repartition_type']),
        (accounts, ['name', 'code', 'account_type', 'company_ids', 'deprecated']),
        (company.step_packing_purchase_journal_id, ['name', 'company_id', 'type', 'currency_id']),
        (contract.partner_id.with_company(company), ['name', 'vat', 'company_id',
                                                    'property_account_payable_id', 'property_account_position_id']),
        (species, ['name', 'company_id', 'type_especie', 'group_especie']),
    ]
    masters_before = [_read(records, names) for records, names in master_sets]
    stock_before = _stock_fingerprint(env, company)
    order_fields = ['state', 'date', 'contract_id', 'valuation_snapshot',
                    'input_picking_id', 'output_picking_id', 'material_picking_id']
    orders_before = _read(orders, order_fields)
    tag_fields = ['name', 'company_id', 'step_tag_kind', 'step_tag_state', 'especie_id',
                  'variedad_id', 'step_tag_line_ids', 'step_actual_kg', 'step_actual_boxes']
    tags_before = _read(tags, tag_fields)
    old_fields = ['name', 'company_id', 'partner_id', 'currency_id', 'invoice_date',
                  'amount_untaxed', 'amount_tax', 'amount_total', 'invoice_line_ids']
    legacy_before = _read(legacy, old_fields)
    old_lines = legacy.invoice_line_ids
    line_fields = ['name', 'product_id', 'product_uom_id', 'quantity', 'price_unit',
                   'account_id', 'tax_ids', 'price_subtotal', 'price_total']
    lines_before = _read(old_lines, line_fields)
    move_ids_before = set(business['account.move'].search([('company_id', '=', company.id)]).ids)

    # New, explicit holding policy only. Existing taxes, prices and accounts stay intact.
    species.with_company(company).write({'step_change_subject_vat': True,
                                        'step_withholding_tax_id': retention.id})
    assert species._fruit_vat_policy_for(company, validate=True) == (True, retention)
    wizard = business['step.packing.monthly.fruit.bill'].create({
        'company_id': company.id, 'date_start': plan['date_start'], 'date_end': plan['date_end'],
        'producer_ids': [(6, 0, contract.partner_id.ids)], 'contract_id': contract.id})
    review_action = wizard.action_prepare_bills()
    assert review_action['res_model'] == 'step.packing.fruit.proforma.migration'
    review = business[review_action['res_model']].browse(review_action['res_id'])
    assert set(review.move_ids.ids) == set(legacy.ids)
    assert all(move.state == 'draft' for move in legacy), 'Review must not cancel documents'
    review.action_move_to_proforma()
    quotes = tags.step_fruit_proforma_id
    assert len(quotes) == 1 and quotes.step_fruit_state == 'draft' and quotes.state == 'draft'
    assert quotes.company_id == company and quotes.partner_id == contract.partner_id
    assert quotes.step_fruit_dte_code == '46' and quotes.step_fruit_withholding_tax_id == retention
    assert set(quotes.step_fruit_tag_ids.ids) == set(tags.ids)
    assert set(quotes.step_fruit_production_ids.ids) == set(orders.ids)
    assert all(move.state == 'cancel' and move.step_fruit_migrated_proforma_id in quotes for move in legacy)
    assert _read(legacy, old_fields) == legacy_before and _read(old_lines, line_fields) == lines_before
    assert set(business['account.move'].search([('company_id', '=', company.id)]).ids) == move_ids_before
    assert not quotes.invoice_ids and not orders.purchase_bill_id
    assert abs(sum(quotes.order_line.mapped('product_qty')) - plan['quantity']) < 0.000001

    quotes.action_fruit_approve()
    invoice_action = quotes.action_fruit_convert()
    bill = quotes.invoice_ids.filtered(lambda move: move.state != 'cancel')
    assert len(bill) == 1 and bill.state == 'draft' and bill.move_type == 'in_invoice'
    assert bill.step_fruit_proforma_id == quotes and set(orders.purchase_bill_id.ids) == set(bill.ids)
    assert bill.company_id == company and bill.journal_id == company.step_packing_purchase_journal_id
    assert bill.currency_id.name == plan['currency']
    assert bill.l10n_latam_document_type_id.code == '46' and not bill.l10n_latam_document_number
    for record in (quotes, bill):
        assert record.currency_id.compare_amounts(record.amount_untaxed, plan['subtotal']) == 0
        assert record.currency_id.compare_amounts(record.amount_tax, plan['tax']) == 0
        assert record.currency_id.compare_amounts(record.amount_total, plan['total']) == 0
    assert set(bill.invoice_line_ids.tax_ids.ids) == set(plan['tax_ids'])
    assert all(line.account_id.code == plan['expense_code'] for line in bill.invoice_line_ids)
    assert company.currency_id.is_zero(sum(bill.line_ids.mapped('balance')))
    assert abs(sum(bill.invoice_line_ids.mapped('quantity')) - plan['quantity']) < 0.000001
    assert _stock_fingerprint(env, company) == stock_before
    assert [_read(records, names) for records, names in master_sets] == masters_before
    assert _read(orders, order_fields) == orders_before and _read(tags, tag_fields) == tags_before
    assert _read(legacy, old_fields) == legacy_before and _read(old_lines, line_fields) == lines_before
    moves_after = set(business['account.move'].search([('company_id', '=', company.id)]).ids)
    assert moves_after - move_ids_before == set(bill.ids)
    assert quotes.action_fruit_convert() == invoice_action
    monthly_action = wizard.action_prepare_bills()
    assert monthly_action['res_model'] == 'purchase.order'
    assert set(tags.step_fruit_proforma_id.ids) == set(quotes.ids)
    assert set(business['account.move'].search([('company_id', '=', company.id)]).ids) == moves_after
    assert _stock_fingerprint(env, company) == stock_before
    return {'review_before_cancellation': True, 'legacy_cancelled_preserved': legacy.ids,
            'proformas': quotes.ids, 'dte': bill.l10n_latam_document_type_id.code,
            'currency': bill.currency_id.name, 'quantity': plan['quantity'],
            'subtotal': bill.amount_untaxed, 'tax': bill.amount_tax, 'total': bill.amount_total,
            'expense_accounts': bill.invoice_line_ids.account_id.mapped('code'),
            'taxes': bill.invoice_line_ids.tax_ids.ids, 'retry_same_invoice': True,
            'monthly_same_proforma': True, 'masters_and_stock_preserved': True,
            'new_species_policy_configured_in_copy_only': True}
