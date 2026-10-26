"""Private full accounting flow with application operator and historical review."""
def verify_flow(root,scoped):
    assert root.cr.dbname.startswith('MANAGEMENT_QA_')
    quiet={'tracking_disable':True,'mail_notrack':True,'mail_notify_force_send':False,'mail_create_nosubscribe':True,'mail_auto_subscribe_no_notify':True}
    setup=root['stock.picking'].with_company(scoped.company).with_context(**quiet).env
    company=scoped.company
    user=setup['res.users'].with_context(no_reset_password=True,tracking_disable=True,mail_create_nosubscribe=True).create({
        'name':'QA114 Packing operación','login':'qa114-probe-op','company_id':company.id,'company_ids':[(6,0,company.ids)],
        'groups_id':[(6,0,[setup.ref('base.group_user').id,setup.ref('step_application_profiles.packing_operation').id])]})
    reader=setup['res.users'].with_context(no_reset_password=True,tracking_disable=True,mail_create_nosubscribe=True).create({
        'name':'QA114 Packing consulta','login':'qa114-probe-read','company_id':company.id,'company_ids':[(6,0,company.ids)],
        'groups_id':[(6,0,[setup.ref('base.group_user').id,setup.ref('step_application_profiles.packing_read').id])]})
    acl=setup['ir.model.access'].with_user(reader).with_context(allowed_company_ids=company.ids)
    assert acl.check('step.packing.production','read') and not acl.check('step.packing.production','write',False)
    assert not acl.check('step.export.forecast','read',False)
    assert not acl.check('stock.picking','create',False)
    def account(code,kind):
        return setup['account.account'].create({'name':'QA122 '+code,'code':code,'account_type':kind,'company_ids':[(6,0,company.ids)]})
    expense=account('QP1221','expense');asset=account('QP1222','asset_current');clearing=account('QP1223','asset_current')
    journal=setup['account.journal'].create({'name':'QA122 comprobante','code':'QP122','type':'general','company_id':company.id})
    category=setup['product.category'].create({'name':'QA122 valuación','property_valuation':'real_time','property_cost_method':'standard',
        'property_stock_valuation_account_id':asset.id,'property_stock_account_input_categ_id':clearing.id,
        'property_stock_account_output_categ_id':clearing.id,'property_account_expense_categ_id':expense.id,'property_stock_journal':journal.id})
    raw=setup['product.product'].create({'name':'QA122 materia prima','is_storable':True,'categ_id':category.id,'standard_price':5})
    finished=setup['product.product'].create({'name':'QA122 resultado','is_storable':True})
    material=setup['product.product'].create({'name':'QA122 material','is_storable':True,'categ_id':category.id,'standard_price':2})
    setup['mrp.bom'].create({'product_tmpl_id':finished.product_tmpl_id.id,'product_qty':1,
                            'bom_line_ids':[(0,0,{'product_id':material.id,'product_qty':1})]})
    producer=setup['res.partner'].create({'name':'QA122 productor'})
    variety=scoped['step.variedad'].search([],limit=1);assert variety
    season=scoped['step.temporada'].search([],limit=1);assert season
    def tag(kind,product,quantity,kilos,result=False):
        return setup['stock.quant.package'].create({'is_fruit_tag':True,'step_tag_kind':kind,'step_packing_result':result,
            'step_producer_id':producer.id,'variedad_id':variety.id,'especie_id':variety.especie_id.id,'step_export_season_id':season.id,
            'step_tag_line_ids':[(0,0,{'product_id':product.id,'producer_id':producer.id,'quantity':quantity,'boxes':quantity,'kilos':kilos})]})
    incoming=tag('C',raw,100,100);incoming.action_step_validate_tag()
    output=tag('E',finished,16,80,'export')
    warehouse=company.step_packing_warehouse_id
    setup['stock.quant']._update_available_quantity(raw,warehouse.lot_stock_id,100,package_id=incoming,owner_id=producer)
    setup['stock.quant']._update_available_quantity(material,company.step_packing_material_location_id,16)
    fixture=setup['step.packing.production'].create({'step_packing_input_tag_ids':[(6,0,incoming.ids)],
                                                   'step_packing_output_tag_ids':[(6,0,output.ids)]})
    require=company.step_packing_require_contract
    setup['res.company'].browse(company.id).step_packing_require_contract=False
    operator=fixture.with_user(user).with_context(allowed_company_ids=company.ids)
    operator.action_step_packing_validate();operator.action_prepare_materials()
    reviewer=fixture.with_env(scoped).with_context(**quiet);reviewer.action_approve_materials()
    operator.action_step_packing_close()
    setup['res.company'].browse(company.id).step_packing_require_contract=require
    assert fixture.state=='closed'
    entries=fixture.material_picking_id.move_ids.stock_valuation_layer_ids.account_move_id
    assert entries.state=='posted'
    assert entries.line_ids.filtered('debit').account_id==expense
    assert entries.line_ids.filtered('credit').account_id==asset
    distribution=entries.line_ids.filtered('debit').analytic_distribution
    ids={int(value) for key in distribution for value in key.split(',')}
    assert len(ids)==3 and sorted(distribution.values())==[100]
    assert not fixture.input_picking_id.move_ids.stock_valuation_layer_ids
    assert len(setup['account.analytic.account'].search([('step_packing_production_id','=',fixture.id)]))==1
    print('T114_T122_OPERATOR_ACCOUNTING_FLOW_OK company=%s operator=%s rollback_required=True'%(company.id,user.id))
    original=scoped['step.packing.production'].with_context(**quiet).search([('name','=','OT/2026/00040')])
    if original:
        entries=(original.input_picking_id.move_ids|original.material_picking_id.move_ids).stock_valuation_layer_ids.account_move_id
        old={line.id:(line.account_id.id,line.debit,line.credit) for line in entries.line_ids}
        original.action_apply_packing_analytics();original.action_apply_packing_analytics()
        assert original.step_analytic_reclassification_ids
        assert all(move.state=='draft' for move in original.step_analytic_reclassification_ids)
        assert {line.id:(line.account_id.id,line.debit,line.credit) for line in entries.line_ids}==old
        assert all(line.analytic_distribution for line in original.step_analytic_reclassification_ids.line_ids.filtered('debit'))
        print('T122_ORIGINAL_DRAFT_RECLASSIFICATION_OK rollback_required=True')
