"""Capture and refresh one reviewed draft without changing its business sources."""
import hashlib
import json
from native_business_profile import scoped_business_environment
from verify_fruit_proforma_case import _stock_fingerprint


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def scoped_order(env, order_id):
    original = env['purchase.order'].browse(order_id).exists()
    assert len(original) == 1
    business = scoped_business_environment(env, company=original.company_id)
    order = business['purchase.order'].browse(order_id)
    order.check_access('write')
    assert not business.su
    return order


def source_snapshot(order):
    return {
        'id': order.id, 'name': order.name, 'company_id': order.company_id.id,
        'partner_id': order.partner_id.id, 'species_id': order.step_fruit_species_id.id,
        'currency_id': order.currency_id.id, 'state': order.state,
        'fruit_state': order.step_fruit_state, 'dte': order.step_fruit_dte_code,
        'retention_id': order.step_fruit_withholding_tax_id.id,
        'tag_ids': sorted(order.step_fruit_tag_ids.ids),
        'production_ids': sorted(order.step_fruit_production_ids.ids),
        'contract_ids': sorted(order.step_fruit_contract_ids.ids),
        'invoice_ids': sorted(order.invoice_ids.ids),
        'period': [str(order.step_fruit_period_start), str(order.step_fruit_period_end)],
        'totals': [order.amount_untaxed, order.amount_tax, order.amount_total],
        'lines': [{'id': line.id, 'product_id': line.product_id.id,
                   'quantity': line.product_qty, 'price': line.price_unit,
                   'discount': line.discount, 'uom_id': line.product_uom.id,
                   'tax_ids': sorted(line.taxes_id.ids),
                   'rows': line.step_fruit_source_rows}
                  for line in order.order_line.sorted('id') if not line.display_type],
    }


def target_policy(order):
    subject, retention = order.step_fruit_species_id._fruit_vat_policy_for(order.company_id, validate=True)
    calculator = order.env['step.packing.monthly.fruit.bill'].new({'company_id': order.company_id.id})
    lines = {}
    net = total = 0.0
    taxes = order.env['account.tax']
    for line in order.order_line.filtered(lambda row: not row.display_type):
        selected = calculator._fruit_tax_ids(line.product_id, subject, retention)
        selected = order.fiscal_position_id.map_tax(selected) if order.fiscal_position_id else selected
        amounts = selected.compute_all(line.price_unit * (1 - line.discount / 100),
            currency=order.currency_id, quantity=line.product_qty,
            product=line.product_id, partner=order.partner_id)
        net += amounts['total_excluded']
        total += amounts['total_included']
        lines[str(line.id)] = sorted(selected.ids)
        taxes |= selected
    assert order.currency_id.compare_amounts(net, order.amount_untaxed) == 0
    return {'dte': '46' if subject else '33', 'retention_id': retention.id,
            'line_taxes': lines, 'totals': [order.currency_id.round(net),
                order.currency_id.round(total - net), order.currency_id.round(total)],
            'tax_fingerprint': fingerprint(taxes.sorted('id').read([
                'name', 'amount', 'amount_type', 'type_tax_use', 'company_id',
                'active', 'price_include', 'invoice_repartition_line_ids', 'refund_repartition_line_ids']))}


def capture(env, order_id):
    assert env.cr.dbname == 'CERRO_EL_PLOMO'
    order = scoped_order(env, order_id)
    assert order.step_fruit_proforma and order.state == order.step_fruit_state == 'draft'
    assert not order.invoice_ids and not order.picking_ids
    return {'ticket': 171, 'reviewed_message_id': 10199,
            'before': source_snapshot(order), 'target': target_policy(order)}


def refresh(env, plan, apply=False):
    assert env.cr.dbname == 'CERRO_EL_PLOMO' or env.cr.dbname.startswith('MANAGEMENT_QA_CERRO_')
    order = scoped_order(env, plan['before']['id'])
    assert source_snapshot(order) == plan['before'], 'The reported draft changed; review its current data'
    assert target_policy(order) == plan['target'], 'The configured tax policy changed after review'
    assert order.state == order.step_fruit_state == 'draft' and not order.invoice_ids
    business, company = order.env, order.company_id
    stock = _stock_fingerprint(business, company)
    account_ids = set(business['account.move'].search([('company_id', '=', company.id)]).ids)
    productions = order.step_fruit_production_ids
    production_rows = productions.sorted('id').read(['state', 'date', 'contract_id', 'valuation_snapshot',
                                                   'purchase_bill_id', 'input_picking_id', 'output_picking_id'])
    original = source_snapshot(order)
    order.action_fruit_refresh_taxes()
    updated = source_snapshot(order)
    unchanged = ('id', 'company_id', 'partner_id', 'species_id', 'currency_id', 'state',
                 'fruit_state', 'tag_ids', 'production_ids', 'contract_ids', 'invoice_ids', 'period')
    assert all(updated[key] == original[key] for key in unchanged)
    assert updated['dte'] == plan['target']['dte']
    assert updated['retention_id'] == plan['target']['retention_id']
    for actual, expected in zip(updated['totals'], plan['target']['totals']):
        assert order.currency_id.compare_amounts(actual, expected) == 0
    for before, after in zip(original['lines'], updated['lines']):
        assert all(before[key] == after[key] for key in ('id', 'product_id', 'quantity', 'price', 'discount', 'uom_id'))
        assert after['tax_ids'] == plan['target']['line_taxes'][str(after['id'])]
        strip_taxes = lambda rows: [{key: value for key, value in row.items() if key != 'tax_ids'} for row in rows]
        assert strip_taxes(before['rows']) == strip_taxes(after['rows'])
    if original['dte'] != updated['dte']:
        assert order.name.startswith('PF' + updated['dte'] + '/')
        assert original['name'] in order.step_fruit_previous_references.splitlines()
    stable = source_snapshot(order)
    order.action_fruit_refresh_taxes()
    assert source_snapshot(order) == stable, 'Refreshing a second time must be a no-op'
    assert _stock_fingerprint(business, company) == stock
    assert productions.sorted('id').read(['state', 'date', 'contract_id', 'valuation_snapshot',
                                         'purchase_bill_id', 'input_picking_id', 'output_picking_id']) == production_rows
    assert set(business['account.move'].search([('company_id', '=', company.id)]).ids) == account_ids
    assert target_policy(order)['tax_fingerprint'] == plan['target']['tax_fingerprint']
    assert not order.invoice_ids and not order.picking_ids
    result = {'id': order.id, 'name': order.name, 'previous_name': original['name'],
              'dte': updated['dte'], 'totals': updated['totals'],
              'draft_only': True, 'sources_preserved': True, 'stock_preserved': True,
              'accounts_preserved': True, 'idempotent': True}
    if apply:
        env.cr.commit()
    return result
