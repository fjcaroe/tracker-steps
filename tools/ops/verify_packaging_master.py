"""T124/T125 native forms, original master domain and existing operator flow."""
import importlib
import json
from pathlib import Path
from lxml import etree
from odoo.tools import config
from native_business_profile import scoped_business_environment

try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    scoped = scoped_business_environment(env)
    previous = config['test_enable']; config['test_enable'] = True
    try:
        from odoo.tests import Form
    finally:
        config['test_enable'] = previous
    arch = etree.fromstring(scoped['product.packaging'].get_view(
        view_id=scoped.ref('step_export.view_step_export_packaging_form').id, view_type='form')['arch'])
    for field in ('step_clamshell_qty', 'step_clamshell_weight_g', 'step_boxes_per_pallet',
                  'step_pallets_per_container', 'step_boxes_per_container_40', 'step_net_pallet_weight'):
        assert arch.xpath("//field[@name='%s']" % field), field
    row = scoped['product.packaging'].search([], limit=1)
    Form(row or scoped['product.packaging'], view='step_export.view_step_export_packaging_form')
    domain = scoped['mrp.bom']._packaging_material_domain()
    assert domain[0][2], 'No native packaging category matched'
    materials = scoped['product.product'].search(domain)
    assert materials, 'Existing business user cannot select any packaging materials'
    menu = scoped.ref('step_packing_packaging_master.menu_packing_fruit_bom')
    assert menu.action == scoped.ref('step_export.action_export_fruit_bom')
    assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
    Form(scoped['mrp.bom'], view='step_export.view_export_fruit_bom_form')
    if env.cr.dbname.startswith('MANAGEMENT_QA_'):
        setup = env(context=dict(env.context, tracking_disable=True, mail_notrack=True,
            mail_create_nosubscribe=True, mail_notify_force_send=False))
        finished = setup['product.product'].create({'name': 'QA T124/T125 product', 'company_id': scoped.company.id})
        package = setup['product.packaging'].create({'name': 'QA T124', 'product_id': finished.id, 'qty': 3.8,
            'step_export_kg_per_box': 3.8, 'step_clamshell_qty': 12, 'step_clamshell_weight_g': 340,
            'step_boxes_per_pallet': 204, 'step_pallets_per_container': 20})
        assert package.step_boxes_per_container_40 == 4080
        assert abs(package.step_net_pallet_weight - 775.2) < 0.00001
        bom = scoped['mrp.bom'].with_context(tracking_disable=True, mail_notrack=True).create({
            'product_tmpl_id': finished.product_tmpl_id.id, 'company_id': scoped.company.id,
            'step_export_fruit': True, 'bom_line_ids': [(0, 0, {'product_id': materials[0].id, 'product_qty': 12})]})
        assert bom.bom_line_ids.product_id == materials[0]
        Form(bom, view='step_export.view_export_fruit_bom_form')
        print('T124_T125_OPERATOR_FLOW_OK rollback_required=True')
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'tickets': [124, 125], 'versions': EXPECTED,
        'existing_profile': scoped.uid, 'company_id': scoped.company.id, 'native_menu_and_form': True,
        'selectable_materials': len(materials), 'writes': False}))
finally:
    env.cr.rollback()
