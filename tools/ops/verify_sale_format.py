"""Transactional sales-user PDF/form/menu verification; samples always rolled back."""
import json
from pathlib import Path
from lxml import etree
from odoo.tests.common import new_test_user

try:
    module = env['ir.module.module'].search([('name', '=', 'step_sale_export_report')])
    assert module.state == 'installed' and module.latest_version == EXPECTED[module.name]
    import odoo.addons.step_sale_export_report as runtime
    assert Path(runtime.__file__).resolve().parent == Path(ROOT)/module.name
    company = env['res.company'].search([('vat', '=', '76943293-0')], limit=1) or env.company
    user = new_test_user(env, login='qa-t62-sale-format', groups='sales_team.group_sale_salesman,sale.group_proforma_sales',
                         company_id=company.id, company_ids=[(6, 0, company.ids)])
    context = dict(allowed_company_ids=company.ids, tracking_disable=True, mail_create_nosubscribe=True, mail_notrack=True)
    company.step_export_sale_format = True
    bank = env['res.bank'].create({'name': 'QA T62 SAMPLE BANK', 'bic': 'TESTUS00', 'step_aba_routing': 'TEST-ABA', 'street': 'QA bank address'})
    account = env['res.partner.bank'].create({'partner_id': company.partner_id.id, 'company_id': company.id,
        'bank_id': bank.id, 'acc_number': 'QA-TEST-ONLY-62', 'acc_holder_name': 'QA T62 BENEFICIARY'})
    company.step_export_bank_id = account
    partner = env['res.partner'].create({'name': 'QA T62 SAMPLE RECEIVER', 'lang': 'es_CL', 'street': 'QA customer address', 'step_export_receiver': True})
    usd = env.ref('base.USD'); usd.active = True
    pricelist = env['product.pricelist'].create({'name': 'QA T62 USD', 'currency_id': usd.id, 'company_id': company.id})
    product_vals = {'name': 'QA T62 SAMPLE FRUIT', 'type': 'service', 'step_export_enabled': True}
    if 'grupo_labor' in env['product.product']._fields:
        product_vals['grupo_labor'] = 'pack'
    product = env['product.product'].create(product_vals)
    shipment = env['step.export.export'].with_company(company).with_context(**context).create({'name': 'QA T62 SHIPMENT'})
    order = env['sale.order'].with_user(user).with_company(company).with_context(**context).create({
        'partner_id': partner.id, 'step_export_sale': True, 'pricelist_id': pricelist.id,
        'step_export_shipment_id': shipment.id, 'note': '<p>QA T62 SAMPLE OBSERVATIONS</p>',
        'incoterm': env['account.incoterms'].search([('code', '=', 'CIF')], limit=1).id,
        'order_line': [(0, 0, {'product_id': product.id, 'product_uom_qty': 10, 'price_unit': 20,
            'discount': 10, 'tax_id': [(5, 0, 0)], 'step_export_kg': 100, 'step_export_boxes': 10}),
            (0, 0, {'product_id': product.id, 'name': 'QA T62 FREIGHT', 'product_uom_qty': 1, 'price_unit': 30,
                'tax_id': [(5, 0, 0)], 'step_export_charge': 'freight'}),
            (0, 0, {'product_id': product.id, 'name': 'QA T62 INSURANCE', 'product_uom_qty': 1, 'price_unit': 5,
                'tax_id': [(5, 0, 0)], 'step_export_charge': 'insurance'})]})
    assert order.amount_total == 215
    view = etree.fromstring(order.get_view(view_type='form')['arch'].encode())
    for field in ('step_export_kg', 'step_export_boxes', 'step_export_charge'):
        assert view.xpath(".//field[@name='order_line']/list/field[@name='%s']" % field)
    assert env.ref('step_export.menu_step_export_sale_orders').action == env.ref('step_export.action_export_sale_orders')
    bindings = env['ir.actions.report'].with_user(user).get_bindings('sale.order')['report']
    assert {env.ref('step_sale_export_report.action_sale_note').id, env.ref('step_sale_export_report.action_proforma').id} <= {r['id'] for r in bindings}
    for action, title in [('action_proforma', b'PROFORMA'), ('action_sale_note', b'NOTA DE VENTA')]:
        if action == 'action_sale_note':
            order.action_confirm()
            assert order.state == 'sale' and order.amount_total == 215
        report = env.ref('step_sale_export_report.'+action).with_user(user)
        html, _ = report._render_qweb_html(report.report_name, order.ids)
        for expected in (title, b'QA T62 SAMPLE FRUIT', b'QA T62 SAMPLE BANK', b'TESTUS00', b'TEST-ABA', b'QA-TEST-ONLY-62', b'QA T62 BENEFICIARY'):
            assert expected in html, expected
        pdf, _ = report._render_qweb_pdf(report.report_name, order.ids)
        assert pdf.startswith(b'%PDF-') and len(pdf) > 10000
        (Path(OUTPUT)/(action+'.pdf')).write_bytes(pdf)
    # Multi-page output must render with repeated headings and intact totals.
    order.order_line = [(0, 0, {'product_id': product.id, 'name': 'QA T62 LONG LINE %02d' % i,
        'product_uom_qty': 1, 'price_unit': 1, 'tax_id': [(5, 0, 0)]}) for i in range(40)]
    report = env.ref('step_sale_export_report.action_proforma').with_user(user)
    pdf, _ = report._render_qweb_pdf(report.report_name, order.ids)
    (Path(OUTPUT)/'multipage.pdf').write_bytes(pdf)
    print('MANAGEMENT_REGISTRY_OK '+json.dumps({'version': module.latest_version,
        'sales_user_form_and_print_menu': True, 'proforma_and_confirmed_sale_pdf': True,
        'discount_freight_insurance_total': 215, 'bank_relation': True, 'multipage': True,
        'samples': 'rolled back'}), flush=True)
finally:
    env.cr.rollback()
