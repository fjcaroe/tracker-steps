"""Native ORM probe: PLAN (private) and COMMIT are supplied by the operator.

Enables inventory only for one unambiguous consumable template/variant, with
all stock, accounting and process rows conserved. Called in a fresh destination
clone first; live caller must own the shared lease and have a verified backup.
"""
import json
from native_business_profile import scoped_business_environment


def enable_inventory(root, scoped, code):
    products=scoped['product.product'].search([('default_code','=',code)])
    assert len(products)==1 and products.type=='consu'
    product=products;template=product.product_tmpl_id
    assert len(template.product_variant_ids)==1
    assert not template.company_id or template.company_id==scoped.company
    template.check_access('write')
    root.cr.execute('SELECT id FROM product_template WHERE id=%s FOR UPDATE',[template.id])
    template.invalidate_recordset()
    before=bool(product.is_storable)
    root.flush_all()
    snapshots={}
    for table in ('stock_quant','stock_move','stock_move_line','stock_picking',
                  'stock_valuation_layer','account_move','account_move_line',
                  'stock_quant_package','step_packing_production'):
        root.cr.execute("SELECT count(*),md5(coalesce(string_agg(to_jsonb(t)::text,'' ORDER BY id),'')) FROM "+table+' t')
        snapshots[table]=root.cr.fetchone()
    root.cr.execute("SELECT md5(coalesce(string_agg((CASE WHEN id=%s THEN to_jsonb(t)-ARRAY['is_storable','write_date','write_uid'] ELSE to_jsonb(t) END)::text,'' ORDER BY id),'')) FROM product_template t",[template.id])
    templates=root.cr.fetchone()
    if not before:
        template.with_context(tracking_disable=True,mail_notrack=True).write({'is_storable':True})
    root.flush_all();root.invalidate_all()
    assert product.is_storable
    for table,expected in snapshots.items():
        root.cr.execute("SELECT count(*),md5(coalesce(string_agg(to_jsonb(t)::text,'' ORDER BY id),'')) FROM "+table+' t')
        assert root.cr.fetchone()==expected,'Unexpected business change: '+table
    root.cr.execute("SELECT md5(coalesce(string_agg((CASE WHEN id=%s THEN to_jsonb(t)-ARRAY['is_storable','write_date','write_uid'] ELSE to_jsonb(t) END)::text,'' ORDER BY id),'')) FROM product_template t",[template.id])
    assert root.cr.fetchone()==templates
    return {'database':root.cr.dbname,'product_id':product.id,'template_id':template.id,
            'before':before,'after':True,'business_unchanged':True,'user':scoped.uid}


if 'PLAN' in globals():
    try:
        assert env.cr.dbname==PLAN['database'] and COMMIT is True
        proof=enable_inventory(env,scoped_business_environment(env),PLAN['product_code'])
        env.cr.commit();env.invalidate_all()
        assert env['product.template'].browse(proof['template_id']).is_storable
        print('PRODUCT_INVENTORY_ENABLED_OK '+json.dumps(proof))
    finally:
        env.cr.rollback()
