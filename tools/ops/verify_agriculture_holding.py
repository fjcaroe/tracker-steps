"""Read effective forms, native actions and the Holding panel with an existing profile."""
import importlib
import json
from pathlib import Path
from lxml import etree
from native_business_profile import scoped_business_environment

try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    scoped = scoped_business_environment(env)
    forms = [
        ('step.packing.order', 'step_packing_operations.view_packing_order_form', 'branch_company_id'),
        ('step.dispatch.guide', 'step_dispatch_guide.view_dispatch_guide_form', 'holding_shipment_company_ids'),
        ('step.export.dispatch.order', 'step_packing_dispatch.instruction_form', 'holding_shipment_company_ids'),
        ('res.partner', 'base.view_partner_form', 'step_export_market_id'),
        ('step.export.export', 'step_export.view_step_export_shipment_form', 'eligible_receiver_ids'),
        ('step.packing.production', 'step_packing_operations.view_packing_production_form', 'step_packing_overweight_kg'),
    ]
    for model, view, field in forms:
        arch = etree.fromstring(scoped[model].get_view(view_id=scoped.ref(view).id, view_type='form')['arch'])
        assert arch.xpath("//field[@name='%s']" % field), (model, field)
    visible = scoped['ir.ui.menu']._visible_menu_ids()
    for xmlid in ('step_packing_operations.action_packing_order', 'step_packing_dispatch.instructions_action'):
        action = scoped['ir.actions.act_window']._for_xml_id(xmlid)
        assert action['res_model'] in ('step.packing.order', 'step.export.dispatch.order')
        assert scoped['ir.ui.menu'].search_count([('id', 'in', list(visible)), ('action', '=', 'ir.actions.act_window,%s' % action['id'])])
        assert all(cid in scoped.user.company_ids.ids for cid in action['context']['allowed_company_ids'])
    panel = scoped['step.packing.order'].operational_comparison('producers')
    assert panel['selected_company_ids'] and panel['companies']
    scoped['step.packing.order'].producer_holding_counts(panel['selected_company_ids'])
    assert len(panel['tables']) == 2
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'tickets': [147, 148, 149, 150, 151], 'versions': EXPECTED,
        'existing_profile': scoped.uid, 'native_menus_forms_panel': True, 'writes': False}))
finally:
    env.cr.rollback()
