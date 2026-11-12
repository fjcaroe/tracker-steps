"""Exercise real customer pallets only in a disposable destination copy; always roll back."""
import json
from odoo import Command
from odoo.tools.safe_eval import safe_eval
from native_business_profile import scoped_business_environment
from odoo.addons.step_export_branch_consolidation.models import branch_companies

assert env.cr.dbname.startswith(('MANAGEMENT_QA_CERRO_', 'MANAGEMENT_QA_QA-CERRO_'))
try:
    root = scoped_business_environment(env).company
    plants = env['res.company'].search([('id', 'child_of', root.id)])
    source_candidates = env['stock.quant.package'].search([('company_id', 'in', plants.ids),
        ('step_tag_state', '=', 'validated'), ('is_fruit_tag', '=', True)]).company_id
    result = None
    for company in source_candidates:
        scoped = scoped_business_environment(env, company=company)
        branches = branch_companies(scoped, company)
        guide_model = scoped['step.dispatch.guide']
        probe = guide_model.new({'company_id': company.id})
        tags = probe.available_load_tag_ids
        if not tags:
            continue
        warehouse = tags[:1].quant_ids.filtered(lambda q: q.quantity > 0).location_id.warehouse_id
        tags = tags.filtered(lambda tag: tag.quant_ids.filtered(lambda q: q.quantity > 0).location_id.warehouse_id == warehouse)
        selected = scoped['stock.quant.package']
        for kind in ('C', 'E', 'N'):
            selected |= tags.filtered(lambda tag: tag.step_tag_kind == kind)[:1]
        if set(selected.mapped('step_tag_kind')) != {'C', 'E', 'N'}:
            continue
        candidates = branches - company
        destination = (candidates.filtered('parent_id') or candidates)[:1]
        dest_warehouse = scoped['stock.warehouse'].with_company(destination).search([('company_id', '=', destination.id)], limit=1)
        if not dest_warehouse:
            continue
        kind = scoped['step.freight.dispatch.type'].search([('step_recipient_kind', '=', 'interplant')], limit=1)
        driver = scoped['res.partner'].create({'name': 'QA native interplant driver', 'step_chofer': True})
        freight = {}
        if kind.paga_flete == 'si':
            route = scoped['step.freight.route'].create({'name': 'QA native interplant route',
                'origin': company.name, 'destination': destination.name, 'company_id': company.id})
            freight = {'freight_paid': True, 'freight_route_id': route.id}
        guide = guide_model.create({'company_id': company.id, 'external_folio': 'QA207-NATIVE-COPY',
            'partner_id': destination.partner_id.id, 'carrier_id': company.partner_id.id,
            'origin_address': 'QA source', 'destination_address': 'QA destination', 'truck_plate': 'QA2070',
            'driver_partner_id': driver.id, 'dispatch_type_id': kind.id,
            'transfer_reason_id': scoped['step.dispatch.transfer.reason'].search([], limit=1).id,
            'step_source_warehouse_id': warehouse.id, 'step_destination_warehouse_id': dest_warehouse.id,
            'load_tag_ids': [Command.set(selected.ids)], **freight})
        guide.action_load_pallet_detail()
        kilos = sum(selected.mapped('step_actual_kg'))
        boxes = sum(selected.mapped('box_count'))
        guide.action_confirm()
        if freight:
            assert guide.freight_order_id.route_id == guide.freight_route_id
        receipt = guide.with_company(destination).step_destination_picking_id
        assert receipt.state not in ('done', 'cancel')
        assert not receipt.step_interplant_tag_ids.quant_ids.filtered(lambda q: q.quantity > 0)
        assert set(receipt.step_interplant_tag_ids.mapped('name')) == set(selected.mapped('name'))
        receipt.with_company(destination).button_validate()
        assert receipt.state == 'done'
        assert abs(sum(receipt.step_interplant_tag_ids.mapped('step_actual_kg')) - kilos) < 0.01
        assert sum(receipt.step_interplant_tag_ids.mapped('box_count')) == boxes
        for line in receipt.move_line_ids:
            original = line.step_interplant_origin_line_id
            assert line.owner_id == original.owner_id
            assert line.lot_id.name == original.lot_id.name
            assert abs(line.quantity_product_uom - original.quantity_product_uom) < 0.000001
        result = {'source': company.id, 'destination': destination.id, 'kinds': ['C', 'E', 'N'],
            'tags': selected.ids, 'kilos': kilos, 'boxes': boxes, 'pending_before_validation': True,
            'owners_lots_stock_conserved': True}
        break
    assert result, 'No real free C/E/N set available in one source warehouse'
    returned = env['stock.picking'].search([('company_id', 'in', plants.ids),
        ('step_fruit_reception_kind', '=', 'process'), ('step_has_fruit_return', '=', True)])
    current = safe_eval(env.ref('step_producer_fruit_reports.action_process').domain)
    assert not env['step.fruit.reception.report'].search(current + [('picking_id', 'in', returned.ids)])
    result['excluded_returns'] = returned.ids
    result['excluded_kilos'] = sum(returned.mapped('step_reception_net_kg'))
    print('INTERPLANT_CUSTOMER_COPY_OK ' + json.dumps(result))
finally:
    env.cr.rollback()
    print('PROBE_ROLLBACK_OK')
