"""Transactional functional probe; never commits sample records or inventory."""
from odoo.exceptions import UserError, ValidationError


def verify_flow(env, operator):
    location = env['stock.warehouse'].search([('company_id', '=', env.company.id)], limit=1).lot_stock_id
    producer = env['res.partner'].create({'name': 'QA T41 proceso transaccional'})
    species = env['step.especie'].create({'name': 'QA T41 fruta', 'type_especie': 'frutal', 'group_especie': 'fruta_h'})
    group = env['step.grupo.variedad'].create({'name': 'QA T41 grupo', 'especie_id': species.id})
    variety = env['step.variedad'].create({'name': 'QA T41 variedad', 'cod_variedad': 'QAT41',
        'especie_id': species.id, 'grupo_variedad_id': group.id})
    raw, export, national, carton = [env['product.product'].create({'name': 'QA T41 ' + name,
        'is_storable': True, 'weight': weight, 'grupo_labor': 'pack'})
        for name, weight in [('granel', 1), ('exportación', 5), ('nacional', 1), ('material', 0)]]
    env['mrp.bom'].create({'product_tmpl_id': export.product_tmpl_id.id, 'product_qty': 1,
        'bom_line_ids': [(0, 0, {'product_id': carton.id, 'product_qty': 1, 'step_export_qty_per_pallet': 2})]})
    incoming = env['stock.quant.package'].create({'is_fruit_tag': True, 'step_tag_kind': 'C',
        'step_producer_id': producer.id, 'especie_id': species.id, 'variedad_id': variety.id,
        'step_tag_line_ids': [(0, 0, {'producer_id': producer.id, 'product_id': raw.id,
            'quantity': 100, 'boxes': 100, 'kilos': 100})]})
    incoming.action_step_validate_tag()
    env['stock.quant']._update_available_quantity(raw, location, 100, package_id=incoming)
    env['stock.quant']._update_available_quantity(carton, location, 18)
    ot = env['step.packing.production'].with_user(operator).create({'raw_product_id': raw.id,
        'fruit_grower_id': producer.id, 'fruit_species_id': species.id, 'fruit_variety_id': variety.id,
        'step_packing_input_tag_ids': [(6, 0, incoming.ids)]})
    for kind, product, qty, kilos in [('E', export, 16, 80), ('N', national, 15, 15)]:
        action = ot.action_create_export_tag() if kind == 'E' else ot.action_create_national_tag()
        env['stock.quant.package'].with_user(operator).with_context(**action['context']).create({
            'box_count': qty, 'step_tag_line_ids': [(0, 0, {'producer_id': producer.id,
                'product_id': product.id, 'quantity': qty, 'boxes': qty, 'kilos': kilos})]})
    ot.invalidate_recordset()
    ot.action_step_packing_validate()
    ot.action_prepare_materials()
    assert ot.material_line_ids.quantity == 18
    try:
        ot.action_approve_materials()
    except UserError:
        pass
    else:
        raise AssertionError('Inventory operator must not approve materials')
    ot.sudo().action_approve_materials()
    ot.action_step_packing_close()
    assert ot.state == 'closed' and ot.step_packing_loss_kg == 5
    assert set(ot.output_picking_id.move_ids.product_id.ids) == {export.id, national.id}
    tag = ot.step_packing_output_tag_ids.filtered(lambda item: item.step_tag_kind == 'E')
    reservation = env['step.export.stock.reservation'].with_user(operator).create({
        'name': 'QA T41 destino', 'destination_country_id': env.ref('base.us').id,
        'step_package_ids': [(6, 0, tag.ids)]})
    reservation.action_step_reserve()
    try:
        with env.cr.savepoint():
            env['step.export.export'].create({'name': 'QA T41 destino incorrecto',
                'destination_country_id': env.ref('base.cl').id, 'tag_ids': [(6, 0, tag.ids)]})
    except ValidationError:
        pass
    else:
        raise AssertionError('Reserved fruit must reject another destination')
    reservation.action_step_release()
    repack = env['step.packing.repack'].with_user(operator).create({'selected_source_ids': [(6, 0, tag.ids)]})
    repack.action_prepare_distribution()
    repack.action_validate()
    assert repack.state == 'done'
    assert repack.target_tag_ids.step_tag_line_ids.source_package_id == tag
    html, _ = env['ir.actions.report']._render_qweb_html('step_packing_operations.report_packing_process', ot.ids)
    assert b'Informe de proceso de Packing' in html
    return {'raw_kg': 100, 'export_kg': 80, 'national_kg': 15, 'loss_kg': 5,
            'materials': 18, 'reservation_wrong_country': 'rejected', 'repack': 'stock moved', 'report': 'rendered'}
