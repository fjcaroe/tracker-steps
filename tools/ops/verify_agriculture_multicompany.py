"""T139/T140: effective native views, selected memberships and existing profile."""
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
    checked = []
    targets = (
        ('step.fundo', 'step_hr.action_step_fundo', 'step_hr.view_step_fundo_form', 'form'),
        ('step.management.fruit.category', 'step_management_costs.action_fruit_category', 'step_fruit_category_unification.category_form', 'form'),
        ('step.management.fruit.class', 'step_management_costs.action_fruit_class', 'step_fruit_category_unification.class_form', 'form'),
        ('step.management.fruit.quality', 'step_inventory_fruit_tag.action_fruit_quality', 'step_inventory_fruit_tag.view_fruit_quality_list', 'list'),
        ('step.fruit.color', 'step_export_client_revision.color_action', 'step_export_client_revision.color_list', 'list'),
    )
    for model_name, action_ref, view_ref, kind in targets:
        model = scoped[model_name]
        action = scoped.ref(action_ref)
        assert action.res_model == model_name
        menus = scoped['ir.ui.menu'].search([('action', '=', 'ir.actions.act_window,%s' % action.id)])
        assert any(m.id in scoped['ir.ui.menu']._visible_menu_ids() for m in menus), model_name
        arch = etree.fromstring(model.get_view(view_id=scoped.ref(view_ref).id, view_type=kind)['arch'])
        assert arch.xpath("//field[@name='company_ids'][@widget='many2many_tags']"), model_name
        assert all(n.get('invisible') in ('1', 'True') for n in arch.xpath("//field[@name='company_id']"))
        assert model._fields['company_ids'].comodel_name == 'res.company'
        assert model.check_access_rights('write', raise_exception=False)
        records = env[model_name].with_context(active_test=False).search([])
        assert all(r.company_id in r.company_ids and r.company_ids for r in records)
        record = model.search([], limit=1)
        if record:
            record.check_access_rule('write')
            if kind == 'form':
                Form(record, view=view_ref)
        checked.append({'model': model_name, 'preserved_records': len(records), 'selected_company_field': True})
    menu = scoped.ref('step_agriculture_multicompany.packing_fundos')
    assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
    assert menu.parent_id == scoped.ref('step_packing_operations.menu_packing_operations_masters')
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'tickets': [139, 140], 'versions': EXPECTED,
        'existing_profile': scoped.uid, 'company_id': scoped.company.id, 'native_menu_and_form': True,
        'masters': checked, 'writes': False}))
finally:
    env.cr.rollback()
