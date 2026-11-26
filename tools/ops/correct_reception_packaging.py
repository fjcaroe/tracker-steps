"""T241: correct explicitly named packaging relations, preserving stock and money.

The private plan records every receipt, original operation, tag and draft source.
Receipt tag rows already point at the correct native packaging. Original stock
products may have been reclassified; retain their product/lot/movement history.
"""
import copy


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_plan(plan):
    require(plan['ticket']==241 and plan['database']=='CERRO_EL_PLOMO','Wrong ticket/destination')
    require(type(plan['user_id']) is int and plan['user_id']>1,'Existing business user required')
    require(type(plan['company_id']) is int and plan['company_id']>0,'Explicit company required')
    names=plan['requested_receipts'];rows=plan['receipts'];missing=plan['missing_receipts']
    require(len(names)==14 and len(set(names))==14,'Fourteen distinct requested receipts required')
    require(rows and len({r['id'] for r in rows})==len(rows),'Distinct existing receipts required')
    require(set(r['name'] for r in rows).isdisjoint(missing)
            and set(r['name'] for r in rows)|set(missing)==set(names),'Incomplete/ambiguous scope')
    require(plan['old_packaging']['id']!=plan['new_packaging']['id'],'Packaging must change')
    require(len({t['id'] for r in rows for t in r['tags']})==sum(len(r['tags']) for r in rows),'Repeated tag')
    for row in rows:
        require(type(row['id']) is int and row['id']>0 and row['name'] in names,'Invalid receipt identity')
        require(row['move_ids'] and len(set(row['move_ids']))==len(row['move_ids'])
                and all(type(k) is int and k>0 for k in row['move_ids']),'Invalid operation identity')
        require(row['tags'] and all(type(t['id']) is int and t['id']>0
                and type(t['row_id']) is int and t['row_id']>0 for t in row['tags']),'Invalid tag identity')


def repair(env, plan):
    from lxml import etree
    from odoo.tools import SQL
    from odoo.addons.step_producer_advances.claims import lock_companies
    from odoo.addons.step_packing_fruit_proforma.purchase import _controlled
    from native_business_profile import scoped_existing_user_environment

    validate_plan(plan)
    require(env.cr.dbname==plan['database'] or env.cr.dbname.startswith('MANAGEMENT_QA_CERRO_t241_'),'Unexpected database')
    company=env['res.company'].browse(plan['company_id'])
    require(company.name==plan['company_name'],'Company differs')
    scoped=scoped_existing_user_environment(env,plan['user_id'],company)
    scoped=scoped(context=dict(scoped.context,tracking_disable=True,mail_notrack=True,
                               mail_create_nosubscribe=True,mail_notify_force_send=False))
    require(scoped.user.has_group('stock.group_stock_manager'),'Existing inventory manager required')
    env.cr.execute("SET LOCAL lock_timeout='10s'")
    lock_companies(company)
    env.cr.execute('LOCK TABLE stock_picking,stock_move,stock_move_line,stock_quant,stock_quant_package,'
                   'step_packing_picking_tag_line,step_fruit_package_line,purchase_order,purchase_order_line '
                   'IN SHARE ROW EXCLUSIVE MODE')
    env.invalidate_all()
    old=scoped['product.packaging'].browse(plan['old_packaging']['id']).exists()
    target=scoped['product.packaging'].browse(plan['new_packaging']['id']).exists()
    require(len(old)==len(target)==1 and old.name==plan['old_packaging']['name']
            and target.name==plan['new_packaging']['name'] and target.product_id.id==plan['new_packaging']['product_id']
            and (not target.company_id or target.company_id in company.parent_ids),'Packaging master differs')
    receipts=scoped['stock.picking'].browse([r['id'] for r in plan['receipts']]).exists()
    require(len(receipts)==len(plan['receipts']),'Missing receipt')
    found=scoped['stock.picking'].search([('name','in',plan['requested_receipts'])])
    require(set(found.ids)==set(receipts.ids),'Requested receipt set changed; inspect missing folios')
    receipts.check_access('write')
    tags=scoped['stock.quant.package'];moves=scoped['stock.move'];rows=scoped['step.packing.picking.tag.line']
    states=[]
    for spec in plan['receipts']:
        receipt=receipts.browse(spec['id'])
        require(receipt.name==spec['name'] and receipt.company_id==company and receipt.state=='done'
                and receipt.step_fruit_reception_kind=='process','Receipt identity/state differs')
        require(set(receipt.move_ids.ids)==set(spec['move_ids'])
                and set(receipt.fruit_tag_line_ids.ids)=={t['row_id'] for t in spec['tags']},'Receipt composition differs')
        for move in receipt.move_ids:
            require(move.state=='done' and not move.move_orig_ids and not move.move_dest_ids,'Movement chain changed')
            require(move.product_packaging_id in old|target,'Unexpected operation packaging')
            states.append(move.product_packaging_id==target)
            moves|=move
        for entry in spec['tags']:
            tag=scoped['stock.quant.package'].browse(entry['id']).exists()
            row=receipt.fruit_tag_line_ids.filtered(lambda r:r.id==entry['row_id'])
            require(len(tag)==len(row)==1 and tag.name==entry['name'] and row.package_id==tag
                    and tag.step_process_reception_id==receipt and tag.company_id==company
                    and tag.step_tag_kind=='C' and tag.step_tag_state==entry['state'],'Tag identity/state differs')
            require(row.packaging_id==target and row.product_id==target.product_id
                    and tag.step_tag_line_ids.product_id==target.product_id,'Corrected product/receipt packaging differs')
            require(tag.step_packaging_id in old|target and tag.box_count==entry['boxes']
                    and row.quantity==entry['boxes'] and round(tag.step_actual_kg,2)==entry['kilos'],'Quantities differ')
            require(not tag.step_packing_production_id and not tag.step_export_shipment_ids
                    and not tag.step_guide_ids and not tag.step_invoice_ids,'Tag has later documents')
            # A previous product correction explains the original operation's
            # product. Keep its ledger; only packaging metadata is being repaired.
            corrections=row.step_product_correction_move_ids.filtered(lambda m:m.step_receipt_correction_direction=='add')
            require(corrections and corrections.product_id==target.product_id and all(m.state=='done' for m in corrections),'Native product correction missing')
            states.append(tag.step_packaging_id==target)
            tags|=tag;rows|=row
    tags.check_access('write');moves.check_access('write')
    drafts=scoped['purchase.order'].search([('step_fruit_proforma','=',True),('step_fruit_state','!=','cancel'),
        ('step_fruit_tag_ids','in',tags.ids)])
    require(set(drafts.ids)=={d['id'] for d in plan['drafts']},'Active proformas changed')
    require(all(d.company_id==company and d.state=='draft' and d.step_fruit_state=='draft'
                and d.step_advance_basis=='received' and d.step_advance_proforma
                and not d.invoice_ids and not d.step_fruit_generated_move_ids for d in drafts),'Only uninvoiced advance drafts may change')
    all_lines=scoped['purchase.order.line'].browse([l['id'] for d in plan['drafts'] for l in d['lines']])
    require(set(all_lines.ids)==set(drafts.order_line.ids),'Draft lines changed')
    lines=all_lines.filtered(lambda line:any(s['tag_id'] in tags.ids for s in line.step_fruit_source_rows or []))
    changes=[];seen=set()
    for line in lines:
        sources=copy.deepcopy(line.step_fruit_source_rows or [])
        affected=[s for s in sources if s['tag_id'] in tags.ids]
        require(affected and len(affected)==len(sources),'Mixed draft packaging requires a separate reviewed plan')
        require(line.step_advance_packaging_id in old|target,'Draft packaging differs')
        states.append(line.step_advance_packaging_id==target)
        for source in affected:
            require(source['tag_id'] not in seen,'Repeated draft source')
            seen.add(source['tag_id'])
            require(source['packaging_id'] in (old.id,target.id),'Source packaging differs')
            states.append(source['packaging_id']==target.id)
            source.update(packaging_id=target.id,packaging_name=target.name)
        changes.append((line,sources))
    require(seen==set(tags.ids),'Missing draft source')
    require(len(set(states))==1,'Partial correction requires review')
    already=all(states)
    if not already:
        # Optimistic concurrency includes financial snapshots and all target rows.
        for table, expected in plan['target_hashes'].items():
            env.cr.execute(SQL('SELECT id,md5(to_jsonb(t)::text) FROM %s t WHERE id=ANY(%s)',
                               SQL.identifier(table),[int(k) for k in expected]))
            require({str(k):v for k,v in env.cr.fetchall()}==expected,'Target changed: '+table)

    def fingerprints():
        result={}
        tables=('stock_picking','stock_move','stock_move_line','stock_quant','stock_quant_package',
                'step_packing_picking_tag_line','step_fruit_package_line','stock_lot','purchase_order','purchase_order_line',
                'account_move','account_move_line','stock_valuation_layer','product_packaging','product_template','res_partner',
                'step_packing_production','step_packing_repack_line','step_harvest_container_transfer',
                'step_harvest_container_transfer_line','mail_mail','mail_notification')
        for table in tables:
            ids=[];excluded=[]
            if table=='stock_move':ids=moves.ids;excluded=['product_packaging_id','write_date','write_uid']
            elif table=='stock_quant_package':ids=tags.ids;excluded=['step_packaging_id','write_date','write_uid']
            elif table=='purchase_order_line':ids=lines.ids;excluded=['step_advance_packaging_id','step_fruit_source_rows','write_date','write_uid']
            env.cr.execute(SQL('SELECT id,md5((to_jsonb(t)-CASE WHEN id=ANY(%s) THEN %s::text[] '
                               'ELSE ARRAY[]::text[] END)::text) FROM %s t ORDER BY id',ids,excluded,SQL.identifier(table)))
            result[table]=dict(env.cr.fetchall())
        return result

    before=fingerprints()
    source_before={l.id:copy.deepcopy(l.step_fruit_source_rows) for l in lines}
    financial_before={d.id:d.read(['state','step_fruit_state','amount_total','amount_untaxed','amount_tax','step_advance_exchange_rate'])[0] for d in drafts}
    boxes_before={r.id:r._step_receipt_totals()['containers'] for r in receipts}
    updated=0
    if not already:
        moves.write({'product_packaging_id':target.id});updated+=len(moves)
        tags.write({'step_packaging_id':target.id});updated+=len(tags)
        for line,sources in changes:
            _controlled(line).write({'step_advance_packaging_id':target.id,'step_fruit_source_rows':sources})
            updated+=1
        for draft in drafts:draft._fruit_check_sources()
    env.flush_all();env.invalidate_all()
    after=fingerprints()
    require(before==after,'Unexpected change beyond packaging metadata; inspect private rehearsal')
    require(financial_before=={d.id:d.read(['state','step_fruit_state','amount_total','amount_untaxed','amount_tax','step_advance_exchange_rate'])[0] for d in drafts},'Financial amounts/workflow changed')
    for line in lines:
        for previous,current in zip(source_before[line.id],line.step_fruit_source_rows):
            require({k:v for k,v in previous.items() if k not in ('packaging_id','packaging_name')}
                    =={k:v for k,v in current.items() if k not in ('packaging_id','packaging_name')},'Source quantities/prices changed')
            require(current['packaging_id']==target.id and current['packaging_name']==target.name,'Draft source not corrected')
    require(boxes_before=={r.id:r._step_receipt_totals()['containers'] for r in receipts},'Physical container total changed')
    visible=scoped['ir.ui.menu']._visible_menu_ids()
    menu=scoped.ref('step_packing_operations.menu_packing_reception_process')
    require(menu.id in visible,'Receipt menu inaccessible')
    view=receipts.get_view(view_type='form')
    require(etree.fromstring(view['arch']).xpath("//field[@name='product_packaging_id']"),'Native receipt form missing packaging')
    receipt_web=receipts.web_read({'name':{},'state':{},'move_ids':{'fields':{'product_packaging_id':{},'quantity':{},'step_fruit_packaging_qty':{}}}})
    for receipt in receipt_web:
        require(all((m['product_packaging_id'] if isinstance(m['product_packaging_id'],int)
                     else m['product_packaging_id']['id'])==target.id for m in receipt['move_ids']),'Native operation web read differs')
    return {'database':env.cr.dbname,'ticket':241,'company_id':company.id,'user_id':scoped.uid,
        'receipts':[{'id':r.id,'name':r.name,'packaging_id':target.id,'boxes':boxes_before[r.id]} for r in receipts],
        'tags':[{'id':t.id,'name':t.name,'receipt_id':t.step_process_reception_id.id,
                 'packaging_id':t.step_packaging_id.id,'kilos':t.step_actual_kg,'boxes':t.box_count} for t in tags],
        'drafts':[{'id':d.id,'name':d.name,'total':d.amount_total,'state':d.step_fruit_state} for d in drafts],
        'missing_receipts':plan['missing_receipts'],'updated_rows':updated,'already_applied':already,
        'stock_quantities_ledger_lots_boxes_preserved':True,'prices_amounts_taxes_exchange_preserved':True,
        'native_menu_form_web_read':True,'notifications_unchanged':True}


if __name__=='__main__':
    from guarded_cerro_data_repair import main
    main('correct_reception_packaging',241)
