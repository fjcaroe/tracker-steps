"""Transactional sales note/proforma probe inside Odoo shell."""
from lxml import etree
from odoo.tests.common import new_test_user
from odoo.tools.safe_eval import safe_eval


def verify_export_sale(env):
    user = new_test_user(env, login='qa-t35-export-sale', groups='sales_team.group_sale_salesman,sale.group_proforma_sales')
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
    assert b'QA T35 export product' in html and b'Pro-Forma' in html
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
        assert ('step_export', '=', True) in safe_eval(node.get('domain'))
    first = env['ir.ui.menu'].search([('parent_id', '=', env.ref('step_export.menu_step_export_shipments').id)], order='sequence,id', limit=1)
    assert first == env.ref('step_export.menu_step_export_shipping_instruction')
    return {'sales_profile': 'Sales User', 'export_draft_in_menu': True,
            'export_product_in_catalog': True, 'ordinary_product_excluded': True,
            'proforma': 'rendered', 'sale': 'confirmed', 'ports': 'native customs master',
            'participant_filter': True, 'instruction_first': True, 'sample_records': 'rolled back'}
