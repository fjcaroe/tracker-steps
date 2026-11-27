"""Recreate one original unit-weighed reception through the native form save and stock validation."""
from odoo.exceptions import UserError


DATABASES=('MANAGEMENT_QA_CERRO_BOM_20261126U42N','COMMUNITY_CERRO_BOM_PACKING_20261127U46A', 'COMMUNITY_CERRO_BOM_PACKING_20261127U46D',
           'COMMUNITY_CERRO_BOM_PACKING_20261127U46C')


def exercise(env):
    return _exercise(env, False)


def containers(env):
    return _exercise(env, True)


def _exercise(env, include_returns):
    assert env.cr.dbname in DATABASES
    actor=env['res.users'].browse(6)
    model=env['stock.picking'].with_user(actor).with_context(lang='en_US',allowed_company_ids=[31])
    source=model.browse(228)
    assert source.state=='done' and source.step_fruit_reception_kind=='process' and source.step_fruit_weighing_by=='unit'
    move=source.move_ids
    tag=source.fruit_tag_line_ids
    original_line=source.move_line_ids
    assert len(move)==len(tag)==len(original_line)==1 and original_line.owner_id==source.fruit_fundo_id.partner_id
    assert original_line.lot_id and original_line.result_package_id==tag.package_id

    vals={name:source[name].id or False for name in ('picking_type_id','location_id','location_dest_id','partner_id',
        'fruit_fundo_id','fruit_species_id','fruit_variety_id','fruit_season_id','step_receiving_packing_id')}
    vals.update(step_fruit_reception_kind='process',step_fruit_weighing_by='unit',step_fruit_weighing_method='manual')
    movement=dict(name='U46 QA',product_id=move.product_id.id,product_uom=move.product_uom.id,
                  location_id=move.location_id.id,location_dest_id=move.location_dest_id.id,
                  product_packaging_id=move.product_packaging_id.id or False,product_uom_qty=move.quantity)
    new_tag={name:tag[name].id or False for name in ('product_id','packaging_id','variety_id','uom_id','category_id','caliber_id')}
    new_tag.update(tag_number='U46-QA-RECEPTION-228',quantity=tag.quantity,kilos=tag.kilos,gross_kg=tag.gross_kg,
                   tare_kg=tag.tare_kg,box_count=tag.box_count,stock_lot_id=original_line.lot_id.id)
    vals.update(move_ids_without_package=[(0,0,movement)],fruit_tag_line_ids=[(0,0,new_tag)])
    assert not model.env['stock.quant.package'].search_count([('name','=',new_tag['tag_number'])])
    created=model.web_save(vals,specification={'id':{}})[0]
    picked=model.browse(created['id'])
    assert picked.state=='draft'
    before=picked.location_dest_id
    try:
        with env.cr.savepoint():
            picked.button_validate()
    except UserError as error:
        assert 'distribuci' in str(error).lower() and 'cantidad recibida' in str(error).lower()
    else:
        raise AssertionError('The reception posted stock with undistributed quantity')
    assert picked.state=='draft' and not picked.fruit_tag_line_ids.package_id
    picked.web_save({'move_ids_without_package':[(1,picked.move_ids.id,{'quantity':move.quantity})]},specification={'id':{}})
    result=picked.button_validate()
    if isinstance(result,dict) and result.get('res_model') in ('stock.backorder.confirmation','stock.immediate.transfer'):
        action_env=model.env[result['res_model']].with_context(**result.get('context',{}))
        wizard=action_env.create({})
        (wizard.process_cancel_backorder if result['res_model']=='stock.backorder.confirmation' else wizard.process)()
    assert picked.state=='done'
    received=picked.fruit_tag_line_ids.package_id
    item=picked.move_line_ids
    assert len(received)==len(item)==1 and received==item.result_package_id and received.name==new_tag['tag_number']
    assert item.lot_id==original_line.lot_id and item.owner_id==original_line.owner_id and item.location_dest_id==before
    assert received.step_tag_state=='validated' and received.step_tag_kind=='C' and received.step_producer_id==item.owner_id
    quants=received.quant_ids.filtered(lambda q:q.quantity>0)
    assert len(quants)==1 and quants.lot_id==item.lot_id and quants.owner_id==item.owner_id and quants.product_id==move.product_id
    outcome=dict(rejected_undistributed=True,user=actor.id,company=source.company_id.id,source=source.id,state=picked.state,
        source_move=move.id,product=move.product_id.id,lot=item.lot_id.id,owner=item.owner_id.id,
        location=item.location_dest_id.id,quantity=item.quantity,stock_quantity=quants.quantity,
        kilos=received.step_actual_kg,boxes=received.box_count,tag_kind=received.step_tag_kind,tag_state=received.step_tag_state,
        linked=received.step_process_reception_id==picked)
    assert outcome['linked']
    if include_returns:
        transfers = picked.step_container_transfer_ids
        for transfer in transfers:
            assert transfer.direction == 'return' and transfer.state == 'draft'
            assert transfer.company_id == picked.company_id and transfer.producer_id == item.owner_id
            assert transfer.warehouse_id == picked.picking_type_id.warehouse_id
        outcome['returns'] = sorted((transfer.direction, transfer.state, transfer.company_id.id,
            transfer.warehouse_id.id, transfer.producer_id.id, line.product_id.id, line.quantity, line.lot_id.id)
            for transfer in transfers for line in transfer.line_ids)
        outcome['return_transfers'] = len(transfers)
    env.cr.rollback()
    return outcome
