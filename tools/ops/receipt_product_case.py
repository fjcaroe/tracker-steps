"""Rehearse, apply and verify the authorized product correction on the native receipt."""
import json

from odoo import Command
from native_business_profile import scoped_business_environment


def verify_rows(receipt, rows, expected_product, owner):
    for plan, line in rows:
        package = line.package_id
        detail = package.step_tag_line_ids
        assert line.picking_id == receipt and line.tag_number == plan['tag']
        assert package.id == plan['package_id'] and package.step_tag_state == 'validated'
        assert package.step_process_reception_id == receipt and package.company_id == receipt.company_id
        assert line.product_id == expected_product and detail.product_id == expected_product
        assert line.stock_lot_id.name == plan['lot_name'] and line.stock_lot_id == detail.lot_id
        assert line.stock_lot_id.product_id == expected_product and line.stock_lot_id.company_id == receipt.company_id
        stock = package.quant_ids.filtered(lambda quant: quant.quantity or quant.reserved_quantity)
        assert len(stock) == 1 and stock.product_id == expected_product and stock.owner_id == owner
        assert stock.location_id == receipt.location_dest_id and stock.lot_id == line.stock_lot_id
        assert abs(stock.quantity - plan['kilos']) < 1e-7 and not stock.reserved_quantity
        assert abs(line.kilos - plan['kilos']) < 1e-7 and abs(detail.kilos - plan['kilos']) < 1e-7
        assert abs(line.quantity - plan['boxes']) < 1e-7 and abs(detail.boxes - plan['boxes']) < 1e-7
        assert line.packaging_id.id == plan['packaging_id']


def run_case(env, plan, phase):
    assert phase in ('rehearse', 'apply', 'verify')
    if phase == 'rehearse':
        assert env.cr.dbname.startswith('MANAGEMENT_QA_CERRO_')
    else:
        assert env.cr.dbname == 'CERRO_EL_PLOMO'
    company = env['res.company'].browse(plan['company_id']).exists()
    business = scoped_business_environment(env, company)
    receipt = business['stock.picking'].browse(plan['receipt_id']).exists()
    assert receipt.name == plan['receipt_name'] and receipt.company_id == company and receipt.state == 'done'
    assert receipt.picking_type_code == 'incoming' and receipt.step_fruit_reception_kind == 'process'
    source = business['product.product'].browse(plan['source_product_id']).exists()
    target = business['product.product'].browse(plan['target_product_id']).exists()
    assert source.default_code == plan['source_code'] and target.default_code == plan['target_code']
    assert source.uom_id == target.uom_id and source.tracking == 'lot'
    owner = business['res.partner'].browse(plan['owner_id']).exists()
    entries = [(row, business['step.packing.picking.tag.line'].browse(row['line_id'])) for row in plan['tags']]
    rows = business['step.packing.picking.tag.line'].browse([line.id for _item, line in entries])
    untouched = [(row, business['step.packing.picking.tag.line'].browse(row['line_id'])) for row in plan['untouched']]
    assert len(entries) == 2 and len(untouched) == 1
    assert set(receipt.fruit_tag_line_ids.ids) == set(rows.ids + [line.id for _item, line in untouched])
    verify_rows(receipt, untouched, source, owner)
    stock_fields = ['product_id', 'quantity', 'owner_id', 'lot_id', 'location_id', 'location_dest_id', 'result_package_id']
    original = receipt.move_line_ids.read(stock_fields)
    move_fields = ['product_id', 'quantity', 'product_uom_qty', 'product_packaging_id', 'step_fruit_packaging_qty']
    original_moves = receipt.move_ids.read(move_fields)
    audit_domain = [('step_receipt_correction_id', '=', receipt.id)]
    moves = business['stock.move']
    if phase != 'verify':
        verify_rows(receipt, entries, source, owner)
        assert not moves.search_count(audit_domain) and target.type == 'consu'
        # The exact authorized master must still be unused, with the audited
        # commercial configuration. Don't convert a product with any history.
        env.cr.execute('SELECT id FROM product_template WHERE id=%s FOR UPDATE', [target.product_tmpl_id.id])
        target.invalidate_recordset()
        assert not target.is_storable and target.tracking == 'none'
        for name in ('stock.move', 'stock.quant', 'account.move.line', 'purchase.order.line', 'sale.order.line'):
            assert not env[name].search_count([('product_id', '=', target.id)], limit=1), name
        target.product_tmpl_id.write({'is_storable': True, 'tracking': 'lot'})
        action = receipt.action_step_correct_c_product()
        wizard = business[action['res_model']].with_context(
            **action['context'], tracking_disable=True, mail_notify_force_send=False).create({
                'line_ids': [Command.set(rows.ids)], 'product_id': target.id, 'reason': 'T196',
            })
        wizard.action_apply()
    assert target.is_storable and target.tracking == 'lot'
    verify_rows(receipt, entries, target, owner)
    verify_rows(receipt, untouched, source, owner)
    assert receipt.move_line_ids.read(stock_fields) == original and receipt.state == 'done'
    assert receipt.move_ids.read(move_fields) == original_moves
    assert sum(receipt.move_ids.mapped('step_fruit_packaging_qty')) == sum(
        item['boxes'] for item, _line in entries + untouched)
    trace = moves.search(audit_domain)
    assert len(trace) == 4 and set(trace.mapped('state')) == {'done'}
    assert not trace.picking_id and not trace.stock_valuation_layer_ids
    assert set(trace.step_receipt_correction_line_id.ids) == set(rows.ids)
    for _plan, line in entries:
        pair = trace.filtered(lambda move: move.step_receipt_correction_line_id == line)
        assert {move.step_receipt_correction_direction: move.product_id for move in pair} == {
            'remove': source, 'add': target}
    return {'phase': phase, 'tags': len(entries), 'kilos': sum(item['kilos'] for item, _line in entries),
            'untouched': len(untouched), 'moves': len(trace), 'owner_and_lots_preserved': True}


if 'CASE' in globals():
    try:
        proof = run_case(env, CASE, PHASE)
        if PHASE == 'apply':
            env.cr.commit()
        print('T196_CASE_OK ' + json.dumps(proof))
    finally:
        env.cr.rollback()
