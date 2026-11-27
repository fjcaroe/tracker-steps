"""Trace Cerro's original fruit receipts to stock operations, owners, packages and tag details as each operator."""
import hashlib
import json

from odoo.exceptions import AccessError


PICKING = ['name','state','company_id','picking_type_id','location_id','location_dest_id','partner_id','fruit_fundo_id',
           'fruit_species_id','fruit_variety_id','scheduled_date','date_done']
MOVE = ['picking_id','company_id','state','product_id','product_uom','product_uom_qty','quantity','location_id','location_dest_id']
ITEM = ['picking_id','move_id','company_id','state','product_id','product_uom_id','quantity','location_id',
        'location_dest_id','lot_id','owner_id','package_id','result_package_id']
TAG = ['picking_id','sequence','tag_number','packaging_id','caliber_id','category_id','quantity','kilos','uom_id']


def signature(rows):
    text=json.dumps(rows,sort_keys=True,default=str)
    return hashlib.sha256(text.encode()).hexdigest()


def capture(env):
    env.cr.execute("SELECT id FROM stock_picking WHERE step_fruit_reception_kind='process' ORDER BY id")
    ids=[record for record, in env.cr.fetchall()]
    assert len(ids)==58
    users=env['res.users'].search([('active','=',True),('share','=',False),('id','!=',1)],order='id')
    results={}
    for actor in users:
        companies=sorted(actor.company_ids.ids)
        for scope in [companies,*([cid] for cid in companies if len(companies)>1)]:
            key=str(actor.id)+'/'+','.join(map(str,scope))
            model=env['stock.picking'].with_user(actor).with_context(allowed_company_ids=scope,lang='en_US')
            try:
                with env.cr.savepoint():
                    visible=model.search([('id','in',ids)],order='id')
                    moves=model.env['stock.move'].search([('picking_id','in',visible.ids)],order='id')
                    items=model.env['stock.move.line'].search([('picking_id','in',visible.ids)],order='id')
                    tags=model.env['step.packing.picking.tag.line'].search([('picking_id','in',visible.ids)],order='id')
                    rows=visible.read(PICKING,load=None)
                    move_rows=moves.read(MOVE,load=None)
                    item_rows=items.read(ITEM,load=None)
                    tag_rows=tags.read(TAG,load=None)
                    # Some profiles present tag/package links through their original stored relation only.
                    env.cr.execute("SELECT id,package_id FROM step_packing_picking_tag_line WHERE id=ANY(%s) ORDER BY id",(tags.ids,))
                    tag_links=env.cr.fetchall()
                    package_ids={pk for _,pk in tag_links if pk}|{item['result_package_id'] for item in item_rows if item['result_package_id']}
                    packages=model.env['stock.quant.package'].search([('id','in',list(package_ids))],order='id')
                    package_rows=packages.read(['name','company_id','variedad_id','fundo_id','step_actual_kg','step_tag_kind',
                                                'step_tag_state','step_producer_id'],load=None)
                    readable=set(packages.ids)
                    payload=[rows,move_rows,item_rows,tag_rows,[(pk,tag if tag in readable else False) for pk,tag in tag_links],package_rows]
                    results[key]=dict(pickings=len(rows),done=sum(row['state']=='done' for row in rows),moves=len(moves),
                        items=len(items),tags=len(tags),packages=len(packages),owned_items=sum(bool(row['owner_id']) for row in item_rows),
                        tracked_items=sum(bool(row['lot_id']) for row in item_rows),digest=signature(payload))
            except AccessError:
                results[key]=dict(denied=True)
    env.cr.rollback()
    return results
