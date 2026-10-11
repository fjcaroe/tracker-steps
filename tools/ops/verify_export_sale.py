"""Transactional sales note/proforma probe inside Odoo shell."""
from lxml import etree
from odoo.tests.common import new_test_user
from odoo.tools.safe_eval import safe_eval


def verify_export_sale(env):
    user = new_test_user(env, login='qa-t35-export-sale', groups='sales_team.group_sale_salesman,sale.group_proforma_sales,stock.group_stock_user')
    receiver = env['res.partner'].create({'name': 'QA T35 receiver', 'step_export_receiver': True, 'lang': 'en_US'})
    product = env['product.product'].create({'name': 'QA T35 export product',
        'type': 'service', 'grupo_labor': 'pack', 'step_export_enabled': True})
    ordinary = env['product.product'].create({'name': 'QA T35 ordinary product',
        'type': 'service', 'grupo_labor': 'pack', 'step_export_enabled': False})
    values = {'partner_id': receiver.id, 'order_line': [(0, 0, {
        'product_id': product.id, 'product_uom_qty': 2, 'price_unit': 50})]}
    action = env.ref('step_export.action_export_sale_orders')
    context = safe_eval(action.context or '{}')
    order = env['sale.order'].with_user(user).with_context(**context).create(values)
    assert order.step_export_sale and order.step_export_sale_context
    assert order.amount_untaxed == 100
    assert order in env['sale.order'].with_user(user).search(safe_eval(action.domain))
    available = env['product.product'].with_user(user).search(order._get_product_catalog_domain())
    assert product in available and ordinary not in available
    tree = etree.fromstring(env['sale.order'].with_user(user).get_view(view_type='form')['arch'].encode())
    apr = ['cod_medidor', 'sector_apr', 'carga_type', 'p_desde', 'p_hasta', 'anterior_apr', 'actual_apr', 'consumo_apr']
    for node in tree.xpath('.//field'):
        if node.get('name') in apr:
            assert 'not step_apr_configured' in node.get('invisible', '')
    html, _ = env['ir.actions.report'].with_user(user)._render_qweb_html('sale.report_saleorder_pro_forma', order.ids)
    custom_format = 'step_export_sale_format' in order.company_id._fields and order.company_id.step_export_sale_format
    title = order._step_export_report_title(True).encode() if custom_format else b'Pro-Forma'
    assert b'QA T35 export product' in html and title in html
    order.action_confirm()
    assert order.state == 'sale' and order.amount_untaxed == 100
    ports = env['l10n_cl.customs_port'].with_user(user).search([], limit=2)
    assert ports
    participant = env['res.partner'].create({'name': 'QA T35 export participant', 'step_export': True})
    shipment = env['step.export.export'].with_user(user).create({'name': 'QA T35 native port selection',
        'carrier_id': participant.id, 'consignee_id': participant.id,
        'origin_port_id': ports[0].id, 'destination_port_id': ports[-1].id})
    assert shipment.origin_port_id == ports[0] and shipment.destination_port_id == ports[-1]
    shipment_tree = etree.fromstring(shipment.get_view(view_type='form')['arch'].encode())
    for name in ('carrier_id', 'consignee_id', 'notify_id', 'freight_forwarder_id', 'customs_agent_id'):
        node = shipment_tree.xpath(".//field[@name='%s']" % name)[0]
        domain = safe_eval(node.get('domain')) if node.get('domain') else shipment._fields[name].domain
        assert ('step_export', '=', True) in domain
    first = env['ir.ui.menu'].search([('parent_id', '=', env.ref('step_export.menu_step_export_shipments').id)], order='sequence,id', limit=1)
    assert first == env.ref('step_export.menu_step_export_shipping_instruction')
    guide = env['step.dispatch.guide'].with_user(user).create({
        'external_folio': 'QA-T35-PACKING-FLOW', 'partner_id': receiver.id,
        'carrier_id': participant.id, 'origin_address': 'QA origin',
        'destination_address': 'QA destination', 'truck_plate': 'QA0035',
        'step_export_shipment_id': shipment.id})
    assert guide in shipment.dispatch_guide_ids
    guide_tree = etree.fromstring(guide.get_view(view_type='form')['arch'].encode())
    assert guide_tree.xpath(".//sheet//field[@name='step_export_shipment_id']")
    packing = env['step.export.packing.list'].with_user(user).create({
        'shipment_id': shipment.id, 'guide_id': guide.id, 'name': False,
        'container_number': 'QA-CONTAINER-35', 'seal_number': 'QA-SEAL-35'})
    assert packing.name.startswith('PL/') and packing.shipment_number == shipment.shipment_number
    html, _ = env['ir.actions.report'].with_user(user)._render_qweb_html(
        'step_export.action_report_export_packing_list', packing.ids)
    assert packing.name.encode() in html and b'QA-CONTAINER-35' in html
    tags = env['stock.quant.package'].with_user(user).with_context(default_step_tag_kind='E').create([
        {'name': 'QA T35 CLAIM TAG A', 'is_fruit_tag': True, 'box_count': 184},
        {'name': 'QA T35 CLAIM TAG B', 'is_fruit_tag': True, 'box_count': 184}])
    shipment.tag_ids = tags
    assert shipment in tags[0].step_export_shipment_ids
    assert tags[0].step_export_shipment_numbers == shipment.shipment_number
    consultation = env.ref('step_export.action_export_consult_tags')
    tag_tree = etree.fromstring(tags.get_view(view_id=consultation.view_id.id, view_type='list')['arch'].encode())
    assert tag_tree.xpath(".//field[@name='step_export_shipment_numbers']")
    if 'step_tag_state' in tags._fields:
        assert tag_tree.xpath(".//field[@name='step_tag_state']")
    claim = env['step.export.customer.claim'].with_user(user).create({
        'name': 'QA T35 detailed claim', 'receiver_id': receiver.id, 'shipment_ids': [(4, shipment.id)]})
    claim.action_load_shipment_tags()
    assert len(claim.line_ids) == 2
    claim.line_ids[0].write({'claimed_amount_usd': 1000, 'accepted_amount_usd': 500})
    claim.line_ids[1].write({'claimed_amount_usd': 1000, 'accepted_amount_usd': 600})
    assert claim.claimed_amount_usd == 2000 and claim.accepted_amount_usd == 1100
    claim.action_accept()
    assert claim.state == 'accepted' and claim in shipment.claim_ids
    return {'sales_profile': 'Sales User', 'export_draft_in_menu': True,
            'export_product_in_catalog': True, 'ordinary_product_excluded': True,
            'proforma': 'rendered', 'sale': 'confirmed', 'ports': 'native customs master',
            'participant_filter': True, 'instruction_first': True,
            'guide_shipment_link': True, 'packing_list': 'saved, numbered and rendered',
            'tag_consultation': True, 'claim_per_tag': '2000 claimed, 1100 accepted',
            'sample_records': 'rolled back'}
