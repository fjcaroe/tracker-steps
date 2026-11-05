"""T166. Apply the approved OT lot labels to existing, never-stocked output tags."""
from odoo.tools import SQL
from repair_reception_lots import preserved_rows


def repair(env, plan):
    assert env.su and plan['ticket'] == 166
    env.cr.execute("""LOCK TABLE stock_picking, stock_move, stock_move_line, stock_quant,
        stock_quant_package, step_fruit_package_line, step_packing_picking_tag_line,
        step_packing_production IN SHARE ROW EXCLUSIVE MODE""")
    env.invalidate_all()
    company = env['res.company'].search([('id', '=', plan['company_id']), ('name', '=', plan['company_name'])])
    assert len(company) == 1
    env = env(context=dict(env.context, allowed_company_ids=company.ids, tracking_disable=True,
                           mail_notrack=True, mail_create_nosubscribe=True, mail_notify_force_send=False))
    orders = env['step.packing.production'].search([
        ('company_id', '=', company.id), ('name', 'in', [item['name'] for item in plan['orders']])], order='name')
    assert len(orders) == len(plan['orders'])
    assert all(order.state in ('created', 'validated') for order in orders)
    targets = orders.step_packing_output_tag_ids.step_tag_line_ids
    assert all(order.step_packing_output_tag_ids for order in orders) and targets
    before = preserved_rows(env, {'step_packing_production': ['step_output_lot_name']})
    protected = {}
    for table, field, ids in (
            ('step_packing_production', 'step_output_lot_name', orders.ids),
            ('step_fruit_package_line', 'lot_id', targets.ids)):
        env.cr.execute(SQL('SELECT id, %s FROM %s WHERE id NOT IN %s ORDER BY id',
                           SQL.identifier(field), SQL.identifier(table), tuple(ids)))
        protected[table] = env.cr.fetchall()
    env.cr.execute('SELECT id, md5(to_jsonb(q)::text) FROM stock_quant q ORDER BY id')
    quants = env.cr.fetchall()
    deliveries = {model: env[model].search([]).ids for model in ('mail.mail', 'mail.notification')}
    audit = []
    for order in orders:
        specification = next(item for item in plan['orders'] if item['name'] == order.name)
        old = order.step_packing_output_tag_ids.step_tag_line_ids.read(['lot_id'])
        order.write({'step_output_lot_name': specification.get('lot') or order.name})
        audit.append({'order_id': order.id, 'order': order.name, 'lot': order.step_output_lot_name,
                      'tags': order.step_packing_output_tag_ids.ids, 'old_detail_lots': old})
        assert all(line.lot_id.name == order.step_output_lot_name and
                   line.lot_id.product_id == line.product_id and line.lot_id.company_id == company
                   for line in order.step_packing_output_tag_ids.step_tag_line_ids)
    env.flush_all()
    after = preserved_rows(env, {'step_packing_production': ['step_output_lot_name']})
    for table, rows in before.items():
        assert all(after[table].get(key) == value for key, value in rows.items()), table
        assert table == 'stock_lot' or rows.keys() == after[table].keys(), table
    for table, field, ids in (
            ('step_packing_production', 'step_output_lot_name', orders.ids),
            ('step_fruit_package_line', 'lot_id', targets.ids)):
        env.cr.execute(SQL('SELECT id, %s FROM %s WHERE id NOT IN %s ORDER BY id',
                           SQL.identifier(field), SQL.identifier(table), tuple(ids)))
        assert env.cr.fetchall() == protected[table], table
    env.cr.execute('SELECT id, md5(to_jsonb(q)::text) FROM stock_quant q ORDER BY id')
    assert env.cr.fetchall() == quants
    assert all(env[model].search([]).ids == ids for model, ids in deliveries.items())
    return {'ticket': 166, 'orders': audit, 'output_tags': len(orders.step_packing_output_tag_ids),
            'quant_rows_preserved': True, 'business_rows_preserved': True}
