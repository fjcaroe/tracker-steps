"""Full T121 flow with the existing company operator; private clones only."""
def verify_flow(root, scoped):
    assert root.cr.dbname.startswith('MANAGEMENT_QA_') and not scoped.su and scoped.uid != 1
    company = scoped.company
    setup = root['stock.picking'].with_company(company).env
    target = company.step_packing_warehouse_id
    source = setup['stock.warehouse'].search([('company_id','=',company.id),('id','!=',target.id)],limit=1)
    assert source
    variety = scoped['step.variedad'].search([],limit=1)
    assert variety
    producer = setup['res.partner'].create({'name':'QA T121 operador'})
    raw, finished, material = [setup['product.product'].create({'name':'QA T121 '+label,'is_storable':True})
                               for label in ('materia prima','exportación','material')]
    setup['mrp.bom'].create({'product_tmpl_id':finished.product_tmpl_id.id,'product_qty':1,
                            'bom_line_ids':[(0,0,{'product_id':material.id,'product_qty':1})]})
    def tag(kind,product,quantity,kilos,result=False):
        return setup['stock.quant.package'].create({'is_fruit_tag':True,'step_tag_kind':kind,
            'step_packing_result':result,'step_producer_id':producer.id,'variedad_id':variety.id,
            'especie_id':variety.especie_id.id,'step_tag_line_ids':[(0,0,{
                'producer_id':producer.id,'product_id':product.id,'quantity':quantity,'boxes':quantity,'kilos':kilos})]})
    incoming = tag('C',raw,100,100); incoming.action_step_validate_tag()
    output = tag('E',finished,16,80,'export')
    setup['stock.quant']._update_available_quantity(raw,source.lot_stock_id,100,package_id=incoming,owner_id=producer)
    setup['stock.quant']._update_available_quantity(material,company.step_packing_material_location_id,16)
    fixture = setup['step.packing.production'].create({'step_packing_input_tag_ids':[(6,0,incoming.ids)],
                                                      'step_packing_output_tag_ids':[(6,0,output.ids)]})
    require_contract = company.step_packing_require_contract
    setup['res.company'].browse(company.id).step_packing_require_contract = False
    ot = fixture.with_env(scoped)
    ot.action_step_packing_validate(); ot.action_prepare_materials(); ot.action_approve_materials(); ot.action_step_packing_close()
    setup['res.company'].browse(company.id).step_packing_require_contract = require_contract
    assert ot.state == 'closed' and ot.step_packing_transfer_id.state == 'done'
    assert ot.step_packing_transfer_id.move_line_ids.owner_id == producer.with_env(scoped)
    assert ot.step_packing_transfer_id.move_line_ids.result_package_id == incoming.with_env(scoped)
    assert ot.material_picking_id.location_id == company.step_packing_material_location_id
    assert ot.input_picking_id.location_id == company.step_packing_fruit_location_id
    assert ot.output_picking_id.location_dest_id == company.step_packing_fruit_location_id
    assert not ot.input_picking_id.move_ids.stock_valuation_layer_ids
    original = scoped['step.packing.production'].search([('name','=','OT/2026/00040')])
    if original and original.state == 'validated' and original.material_review_state == 'approved':
        unsupported = original.step_packing_output_tag_ids.step_tag_line_ids.product_id.filtered(lambda p: not p.is_storable)
        if unsupported:
            from odoo.exceptions import UserError
            for row in original.material_line_ids:
                quants = scoped['stock.quant'].search([('product_id','=',row.product_id.id),
                    ('location_id','=',company.step_packing_material_location_id.id),('owner_id','=',False),
                    ('package_id','=',False),('company_id','=',company.id),('quantity','>',0)])
                assert sum(q.quantity-q.reserved_quantity for q in quants) >= row.quantity
            try:
                original.action_step_packing_close()
            except UserError as exc:
                assert 'controlar inventario' in str(exc)
            else:
                raise AssertionError('Non-inventory fruit unexpectedly closed')
            assert original.state == 'validated' and not original.step_packing_transfer_id
            print('T121_ORIGINAL_MATERIAL_STOCK_OK pending_product_definition=True writes=False')
        else:
            original.action_step_packing_close()
            assert original.state == 'closed'
            assert original.material_picking_id.location_id == company.step_packing_material_location_id
            assert original.input_picking_id.location_id == company.step_packing_fruit_location_id
            assert original.step_packing_transfer_id.state == 'done'
            assert original.material_picking_id.move_ids and original.output_picking_id.state == 'done'
            print('T121_ORIGINAL_OT_REPLAY_OK rollback_required=True')
    print('T121_OPERATOR_FLOW_OK uid=%s company=%s rollback_required=True' % (scoped.uid,company.id))
