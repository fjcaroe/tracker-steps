"""Verify an unchanged customer case inside a disposable destination copy."""
from native_business_profile import scoped_business_environment


def verify_case(env, plan):
    assert env.cr.dbname.startswith('MANAGEMENT_QA_CERRO_'), 'Customer fixtures are copy-only'
    company = env['res.company'].browse(plan['company_id']).exists()
    business = scoped_business_environment(env, company=company)
    assert business.companies == company and not business.su
    contract = business['step.producer.purchase.contract'].browse(plan['contract_id']).exists()
    contract.check_access('read')
    orders = business['step.packing.production'].search([
        ('company_id', '=', company.id), ('fruit_grower_id', '=', contract.partner_id.id),
        ('date', '>=', plan['date_start']), ('date', '<=', plan['date_end']),
        ('state', 'in', ['closed', 'costed', 'accounted'])])
    assert orders and set(orders.ids) == set(plan['order_ids'])
    assert not orders.purchase_bill_id, 'Use a fresh case without previous billing'
    fields = ['state', 'contract_id', 'valuation_snapshot']
    before = orders.read(fields)
    layers = orders.output_picking_id.move_ids.stock_valuation_layer_ids
    valuation = layers.read(['quantity', 'value', 'remaining_qty', 'remaining_value'])
    contract_before = contract.product_line_ids.read(['product_id', 'price_unit', 'debit_account_id'])
    wizard = business['step.packing.monthly.fruit.bill'].create({
        'company_id': company.id, 'date_start': plan['date_start'], 'date_end': plan['date_end'],
        'producer_ids': [(6, 0, contract.partner_id.ids)], 'contract_id': contract.id})
    action = wizard.action_prepare_bills()
    bills = orders.purchase_bill_id
    assert len(bills) == 1 and bills.state == 'draft' and bills.company_id == company
    assert bills.currency_id.name == plan['currency']
    assert abs(bills.amount_untaxed - plan['subtotal']) < bills.currency_id.rounding
    assert abs(sum(bills.invoice_line_ids.mapped('quantity')) - plan['quantity']) < 0.00001
    for line in bills.invoice_line_ids:
        assert line.account_id.code == plan['expense_code']
        assert line.tax_ids == line._get_computed_taxes(), 'Do not discard inherited or fiscal-position taxes'
    assert set(bills.invoice_line_ids.tax_ids.ids) == set(plan['tax_ids'])
    assert abs(bills.amount_tax - plan['tax']) < bills.currency_id.rounding
    assert abs(bills.amount_total - plan['total']) < bills.currency_id.rounding
    assert bills.company_id.currency_id.is_zero(sum(bills.line_ids.mapped('balance')))
    assert bills.line_ids.filtered(lambda line: line.display_type == 'payment_term').account_id
    invoice_view = bills.get_view(view_type='form')['arch']
    assert 'invoice_line_ids' in invoice_view and 'journal_id' in invoice_view
    count = business['account.move'].search_count([('move_type', '=', 'in_invoice')])
    assert wizard.action_prepare_bills()['domain'] == action['domain']
    assert business['account.move'].search_count([('move_type', '=', 'in_invoice')]) == count
    assert orders.read(fields) == before
    assert layers.read(['quantity', 'value', 'remaining_qty', 'remaining_value']) == valuation
    assert contract.product_line_ids.read(['product_id', 'price_unit', 'debit_account_id']) == contract_before
    return {'branch_only': True, 'contract': contract.name, 'orders': orders.mapped('name'),
            'currency': bills.currency_id.name, 'subtotal': bills.amount_untaxed,
            'tax': bills.amount_tax, 'total': bills.amount_total,
            'accounts': bills.invoice_line_ids.account_id.mapped('code'),
            'taxes': bills.invoice_line_ids.tax_ids.ids, 'retry_same_draft': True,
            'masters_and_stock_preserved': True}
