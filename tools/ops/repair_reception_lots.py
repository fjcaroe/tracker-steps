"""T165. Relabel approved receipts through native stock corrections in one transaction."""
from odoo.tools import SQL
from odoo.tools.float_utils import float_compare


def preserved_rows(env):
    result = {}
    tables = {
        'stock_picking': [], 'stock_move': [], 'stock_quant_package': [],
        'stock_move_line': ['lot_id'],
        'step_fruit_package_line': ['lot_id'],
        'step_packing_picking_tag_line': ['stock_lot_id'],
        'step_packing_production': [], 'account_move': [], 'account_move_line': [],
        'stock_valuation_layer': [], 'stock_lot': [],
    }
    for table, excluded in tables.items():
        excluded += ['write_date', 'write_uid']
        env.cr.execute(SQL(
            "SELECT id, md5((to_jsonb(t) - %s::text[])::text) FROM %s t ORDER BY id",
            excluded, SQL.identifier(table)))
        result[table] = dict(env.cr.fetchall())
    return result


def stock_totals(env, products):
    env.flush_all()
    env.cr.execute("""
        SELECT product_id, location_id, package_id, owner_id, company_id,
               SUM(quantity), SUM(reserved_quantity)
          FROM stock_quant WHERE product_id IN %s
         GROUP BY product_id, location_id, package_id, owner_id, company_id
    """, [tuple(products.ids)])
    return {tuple(row[:5]): (float(row[5]), float(row[6])) for row in env.cr.fetchall()}


def repair(env, plan):
    assert env.su and plan['ticket'] == 165
    env.cr.execute("""LOCK TABLE stock_picking, stock_move, stock_move_line, stock_quant,
        stock_quant_package, step_fruit_package_line, step_packing_picking_tag_line,
        step_packing_production IN SHARE ROW EXCLUSIVE MODE""")
    env.invalidate_all()
    company = env['res.company'].search([('id', '=', plan['company_id']), ('name', '=', plan['company_name'])])
    assert len(company) == 1
    env = env(context=dict(env.context, allowed_company_ids=company.ids, tracking_disable=True,
                           mail_notrack=True, mail_create_nosubscribe=True, mail_notify_force_send=False))
    receipts = env['stock.picking']
    lots_by_package = {}
    rows_by_package = {}
    for specification in plan['receipts']:
        picking = receipts.search([('name', '=', specification['name']), ('company_id', '=', company.id)])
        assert len(picking) == 1 and picking.state == 'done' and picking.step_fruit_reception_kind == 'process'
        assert (picking.fruit_lot or '').strip() == specification['lot']
        assert picking.fruit_tag_line_ids
        receipts |= picking
        for row in picking.fruit_tag_line_ids:
            tag = row.package_id
            assert tag and tag.is_fruit_tag and tag.step_tag_kind == 'C'
            assert tag.step_process_reception_id == picking
            assert row.product_id and len(tag.step_tag_line_ids) == 1
            assert tag.step_tag_line_ids.product_id == row.product_id
            assert row.product_id.is_storable
            assert tag.id not in lots_by_package
            lots_by_package[tag.id] = (row.product_id, specification['lot'])
            rows_by_package[tag.id] = row

    # Carry the corrected origin through C-tag splits, using actual stock links.
    pending = list(lots_by_package)
    moves = env['stock.move.line']
    while pending:
        tag_id = pending.pop()
        product, name = lots_by_package[tag_id]
        linked = moves.search(['|', ('package_id', '=', tag_id), ('result_package_id', '=', tag_id)])
        assert linked and all(line.company_id == company and line.product_id == product for line in linked)
        assert all(line.state in ('done', 'cancel') for line in linked)
        moves |= linked.filtered(lambda line: line.state == 'done')
        for child in linked.filtered(lambda line: line.package_id.id == tag_id and line.state == 'done').result_package_id:
            assert child.is_fruit_tag and child.step_tag_kind == 'C'
            expected = lots_by_package.get(child.id)
            assert not expected or expected == (product, name), 'A split merges different receipt lots'
            if not expected:
                lots_by_package[child.id] = (product, name)
                pending.append(child.id)
    tags = env['stock.quant.package'].browse(list(lots_by_package))
    assert not any(q.reserved_quantity for q in tags.quant_ids)
    for tag in tags:
        origins = moves.filtered(lambda line: line.result_package_id == tag)
        root_row = rows_by_package.get(tag.id)
        assert all((root_row and line.picking_id == root_row.picking_id and not line.package_id)
                   or line.package_id.id in lots_by_package for line in origins)
        assert len(tag.step_tag_line_ids) == 1
        assert tag.step_tag_line_ids.product_id == lots_by_package[tag.id][0]

    products = tags.step_tag_line_ids.product_id
    before_rows = preserved_rows(env)
    before_stock = stock_totals(env, products)
    before_deliveries = {model: env[model].search([]).ids for model in ('mail.mail', 'mail.notification')}
    audit = []
    native_lots = {}
    for tag in tags:
        product, name = lots_by_package[tag.id]
        root = receipts.filtered(lambda p: (p.fruit_lot or '').strip() == name
                                 and product in p.fruit_tag_line_ids.product_id)[:1]
        lot = root._process_receipt_lot(product)
        native_lots[tag.id] = lot
        audit.append({'tag_id': tag.id, 'tag': tag.name, 'lot': lot.name,
                      'old_detail_lots': tag.step_tag_line_ids.lot_id.ids})
    for line in moves.sorted(lambda line: (line.date, line.id)):
        source = native_lots.get(line.package_id.id)
        target = native_lots.get(line.result_package_id.id)
        assert not source or not target or source == target
        lot = source or target
        assert lot
        if line.lot_id != lot:
            line.with_company(company).write({'lot_id': lot.id})
    # Historical validated tag details are immutable in the operator flow.
    # This versioned, explicitly scoped repair updates only their lot relation.
    for tag in tags:
        lot = native_lots[tag.id]
        env.cr.execute('UPDATE step_fruit_package_line SET lot_id=%s WHERE package_id=%s', [lot.id, tag.id])
        row = rows_by_package.get(tag.id)
        if row:
            env.cr.execute('UPDATE step_packing_picking_tag_line SET stock_lot_id=%s WHERE id=%s', [lot.id, row.id])
    env.invalidate_all()
    after_rows = preserved_rows(env)
    for table, rows in before_rows.items():
        assert all(after_rows[table].get(key) == value for key, value in rows.items()), table
        assert table == 'stock_lot' or rows.keys() == after_rows[table].keys(), table
    after_stock = stock_totals(env, products)
    for key in before_stock.keys() | after_stock.keys():
        product = products.browse(key[0])
        for old, new in zip(before_stock.get(key, (0, 0)), after_stock.get(key, (0, 0))):
            assert not float_compare(old, new, precision_rounding=product.uom_id.rounding), key
    for tag in tags:
        lot = native_lots[tag.id]
        assert tag.step_tag_line_ids.lot_id == lot
        assert all(q.lot_id == lot for q in tag.quant_ids if q.quantity or q.reserved_quantity)
        row = rows_by_package.get(tag.id)
        assert not row or row.stock_lot_id == lot
        tag.step_tag_line_ids._check_lot()
    assert all(env[model].search([]).ids == ids for model, ids in before_deliveries.items())
    return {'ticket': 165, 'receipts': receipts.ids, 'tags': audit, 'move_lines': moves.ids,
            'orders': env['step.packing.production'].search([('step_packing_input_tag_ids', 'in', tags.ids)]).ids,
            'stock_totals_preserved': True, 'business_rows_preserved': True}
