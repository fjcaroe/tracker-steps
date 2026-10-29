"""Full stock reception with an existing operator, exclusively in private clones.

Caller must roll back the entire shell transaction after verification.
"""
def verify_flow(root, scoped):
    assert root.cr.dbname.startswith('MANAGEMENT_QA_')
    assert scoped.uid != 1 and not scoped.su
    setup = root['stock.picking'].with_company(scoped.company).env
    company = scoped.company
    warehouse = setup['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
    producer = setup['res.partner'].create({'name': 'QA T120 flujo privado', 'is_productor': True})
    fundo = setup['step.fundo'].create({'name': 'QA T120 flujo privado', 'partner_id': producer.id,
                                       'company_id': company.id})
    species = setup['step.especie'].search([], limit=1)
    kg = setup.ref('uom.product_uom_kgm')
    product = setup['product.product'].create({'name': 'QA T120 flujo kg', 'is_storable': True,
                                              'uom_id': kg.id, 'uom_po_id': kg.id})
    packaging = setup['product.packaging'].create({'name': 'QA T120 8kg', 'product_id': product.id, 'qty': 8})
    picking = setup['stock.picking'].create({
        'partner_id': producer.id, 'picking_type_id': warehouse.in_type_id.id,
        'location_id': warehouse.in_type_id.default_location_src_id.id,
        'location_dest_id': warehouse.lot_stock_id.id, 'step_fruit_reception_kind': 'process',
        'fruit_fundo_id': fundo.id, 'fruit_species_id': species.id,
        'step_fruit_type': 'conventional', 'step_fruit_gross_kg': 400})
    move = setup['stock.move'].create({
        'name': 'QA T120 flujo', 'picking_id': picking.id, 'product_id': product.id,
        'product_uom': kg.id, 'product_uom_qty': 400, 'product_packaging_id': packaging.id,
        'location_id': picking.location_id.id, 'location_dest_id': picking.location_dest_id.id})
    move._action_confirm(merge=False); move.quantity = 400
    for index, kilos in enumerate((160, 240)):
        setup['step.packing.picking.tag.line'].create({
            'picking_id': picking.id, 'tag_number': 'QA120-FLOW-%s-%s' % (picking.id, index),
            'quantity': kilos / 8, 'kilos': kilos, 'packaging_id': packaging.id})
    # A physical 50-box count survives a correction of measured kilograms.
    assert move.step_fruit_packaging_qty==50
    move.quantity=401
    assert move.step_fruit_packaging_qty==50
    move.quantity=400
    print('T132_WEIGHT_CORRECTION_PRESERVES_CONTAINERS_OK')
    operator = picking.with_env(scoped)
    operator.button_validate()
    assert operator.state == 'done'
    assert sum(operator.move_line_ids.mapped('quantity')) == 400
    assert operator.move_line_ids.owner_id == producer.with_env(scoped)
    assert len(operator.fruit_tag_line_ids.package_id) == 2
    assert all(tag.step_tag_state == 'validated' for tag in operator.fruit_tag_line_ids.package_id)
    assert not operator.move_ids.stock_valuation_layer_ids
    actual = scoped['stock.picking'].search([('name', '=', 'FRU/IN/00008'),
                                            ('step_fruit_reception_kind', '=', 'process')])
    if actual and actual.state == 'assigned' and actual.fruit_tag_line_ids.tag_number == 'C199':
        original_package = actual.fruit_tag_line_ids.package_id
        actual.button_validate()
        assert actual.state == 'done' and actual.fruit_tag_line_ids.package_id == original_package
        assert sum(actual.move_line_ids.mapped('quantity')) == 400
        assert original_package.step_tag_line_ids.quantity == 400
        assert original_package.step_actual_kg == 400 and original_package.box_count == 50
        print('T120_ORIGINAL_RECEIPT_REPLAY_OK rollback_required=True')
    print('T120_OPERATOR_FLOW_OK uid=%s company=%s rollback_required=True' % (scoped.uid, company.id))
