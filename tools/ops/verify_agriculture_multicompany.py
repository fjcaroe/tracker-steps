"""T139/T140: effective native views, selected memberships and existing profile."""
import importlib
import json
from pathlib import Path
from lxml import etree
from odoo.tools import config
from native_business_profile import scoped_business_environment


def verify_calibers(env):
    records = env['step.management.fruit.caliber'].with_context(active_test=False).search([])
    groups = env['step.management.caliber.group'].with_context(active_test=False).search([])
    assert all(r.company_id in r.company_ids for r in records | records.browse())
    assert all(r.company_id in r.company_ids for r in groups)
    assert all(not (r.company_ids - r.group_id.company_ids) for r in records)
    sample = records.filtered('active')[:1]
    business = scoped_business_environment(env, company=sample.company_id if sample else None)
    model = business['step.management.fruit.caliber']
    menu = business.ref('step_packing_operations.menu_packing_config_fruit_caliber')
    assert menu.id in business['ir.ui.menu']._visible_menu_ids()
    assert menu.action.res_model == model._name
    for kind in ('list', 'form'):
        arch = etree.fromstring(model.get_view(view_type=kind)['arch'])
        assert arch.xpath("//field[@name='company_ids'][@widget='many2many_tags']")
    for ref in ('step_management_costs.rule_fruit_caliber_company',
                'step_management_costs.rule_caliber_group_company'):
        assert "company_ids" in business.ref(ref).domain_force
    if sample:
        rows = model.browse(sample.id).web_read({
            'name': {}, 'company_ids': {'fields': {'display_name': {}}},
            'group_id': {'fields': {'display_name': {}}},
            'step_contract_caliber_id': {'fields': {'display_name': {}}}})
        assert rows[0]['id'] == sample.id
        assert sample.id in model.search([('id', '=', sample.id)]).ids
    return {'ticket': 200, 'native_menu_list_and_form': True,
            'preserved_calibers': len(records), 'preserved_groups': len(groups)}

def verify_contact_group(scoped):
    producer_menu = scoped.ref('step_packing_operations.menu_packing_master_producers')
    farm_menu = scoped.ref('step_agriculture_multicompany.packing_fundos')
    visible = scoped['ir.ui.menu']._visible_menu_ids()
    assert producer_menu.id in visible and farm_menu.id in visible
    producer = scoped[producer_menu.action.res_model]
    farm = scoped[farm_menu.action.res_model]
    assert producer._fields['step_contact_group_id'].comodel_name == 'res.partner'
    assert farm._fields['step_contact_group_id'].comodel_name == 'res.partner'
    form = etree.fromstring(producer.get_view(view_type='form')['arch'])
    node, = form.xpath("//page[@name='productor']//field[@name='step_contact_group_id']")
    assert "('is_productor', '=', True)" in node.get('domain')
    nested_farms, = form.xpath("//page[@name='productor']//field[@name='step_export_fundo_ids']/list")
    assert nested_farms.get('default_order')
    partner_list = etree.fromstring(producer.get_view(view_type='list')['arch'])
    farm_list = etree.fromstring(farm.get_view(view_type='list')['arch'])
    assert 'default_is_productor' in producer_menu.action.context
    assert partner_list.xpath("//list/field[@name='step_contact_group_id'][@optional='show']")
    assert farm_list.xpath("//list/field[@name='step_contact_group_id'][@optional='show']")
    sample = farm.search([('partner_id.is_productor', '=', True)], limit=1)
    if sample:
        sample.web_read({'step_contact_group_id': {'fields': {'display_name': {}}}})
    return {'ticket': 211, 'producer_form': True, 'producer_list': True, 'farm_list': True}


try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    for rule_ref in ('step_producers.rule_step_producer_fundo_company',
                     'step_management_costs.rule_fruit_category_company',
                     'step_management_costs.rule_fruit_class_company',
                     'step_export_client_revision.color_company',
                     'step_agriculture_multicompany.quality_company'):
        rule = env.ref(rule_ref)
        assert rule.active and rule.domain_force.replace('"', "'").replace(' ', '') == "[('company_ids','in',company_ids)]", rule_ref
    scoped = scoped_business_environment(env)
    previous = config['test_enable']; config['test_enable'] = True
    try:
        from odoo.tests import Form
    finally:
        config['test_enable'] = previous
    checked = []
    targets = (
        ('step.fundo', 'step_producers.action_step_producers_fundo', 'step_hr.view_step_fundo_form', 'form'),
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
            else:
                form_ref = 'step_agriculture_multicompany.' + ('quality_form' if model_name.endswith('.quality') else 'color_form')
                form_arch = etree.fromstring(model.get_view(view_id=scoped.ref(form_ref).id, view_type='form')['arch'])
                assert form_arch.xpath("//field[@name='company_ids']")
                Form(record, view=form_ref)
        checked.append({'model': model_name, 'preserved_records': len(records), 'selected_company_field': True})
    menu = scoped.ref('step_agriculture_multicompany.packing_fundos')
    assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
    assert menu.parent_id == scoped.ref('step_packing_operations.menu_packing_operations_masters')
    proof = {'tickets': [139, 140], 'versions': EXPECTED,
        'existing_profile': scoped.uid, 'company_id': scoped.company.id, 'native_menu_and_form': True,
        'masters': checked, 'writes': False}
    if env.ref('step_agriculture_multicompany.partner_company_read', raise_if_not_found=False):
        from verify_shared_producer_reception import verify_shared_producer_reception
        proof['tickets'].append(194)
        proof['shared_producer'] = verify_shared_producer_reception(env, scoped, SHARED_PRODUCER_RECEPTION)
    if 'company_ids' in env['step.management.fruit.caliber']._fields:
        proof['shared_calibers'] = verify_calibers(env)
    if 'step_contact_group_id' in scoped['res.partner']._fields:
        proof['producer_group'] = verify_contact_group(scoped)
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps(proof))
finally:
    env.cr.rollback()
