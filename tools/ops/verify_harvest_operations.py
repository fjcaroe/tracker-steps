"""T101/T102 effective action, nested field and existing-record checks."""
import importlib
import json
from pathlib import Path
from lxml import etree


def check_fields(model, node):
    for child in node:
        if child.tag == 'field':
            field = env[model]._fields.get(child.get('name'))
            assert field, (model, child.get('name'))
            if field.relational:
                for view in child:
                    if view.tag in ('form', 'list', 'kanban'):
                        check_fields(field.comodel_name, view)
        elif child.tag != 'templates':
            check_fields(model, child)


try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    menu = env.ref('step_cosecha.menu_step_cosecha_proceso')
    assert menu.parent_id == env.ref('step_cosecha.menu_step_cosecha_recepcion')
    assert menu.action == env.ref('step_cosecha.action_step_cosecha_proceso')
    for key, model in [('fruit_class', 'step.management.fruit.class'),
                       ('tag_state', 'step.packing.tag.state'),
                       ('tag_type', 'step.packing.tag.type')]:
        item = env.ref('step_cosecha_operations.menu_' + key)
        assert item.active and item.parent_id == env.ref('step_cosecha.menu_step_cosecha_config')
        assert item.action.res_model == model
        for kind in ('list', 'form'):
            assert env[model].get_view(view_type=kind)['arch']
    for model, ref in [('hr.salary.custom', 'step_hr.view_hr_salary_custom_form'),
                       ('step.cosecha.registry', 'step_cosecha.view_step_cosecha_registry_form')]:
        arch = etree.fromstring(env[model].get_view(view_id=env.ref(ref).id, view_type='form')['arch'])
        check_fields(model, arch)
        if model == 'hr.salary.custom':
            header = arch.xpath("//sheet/group/group/field[@name='partner_id']")[0]
            assert header.get('invisible') == "group_type != 'contratista'"
            assert not arch.xpath("//field[@name='contract_line']/list/field[@name='partner_id']")
        else:
            # Read representative real records through the web client's serializer.
            records = env[model].search([('type_tarea', '=', 'contratista')], limit=5)
            records.web_read({'name': {}, 'partner_id': {'fields': {'display_name': {}}},
                              'salary_id_contrac': {'fields': {'display_name': {}}},
                              'registry_tarja_line': {'fields': {'employee_id': {'fields': {'display_name': {}}}}}})
    tariff_view = env.ref('step_cosecha_operations.harvest_pricelist_form')
    assert not tariff_view.inherit_id, 'Harvest uses its own versioned native form'
    tariff_arch = etree.fromstring(env['product.pricelist'].get_view(
        view_id=tariff_view.id, view_type='form')['arch'])
    check_fields('product.pricelist', tariff_arch)
    assert not tariff_arch.xpath(".//field[starts-with(@name, 'x_')]")
    for field in ('labor_id', 'uom_id'):
        assert tariff_arch.xpath("//field[@name='item_ids']/list/field[@name='%s']" % field)
        assert tariff_arch.xpath("//field[@name='item_ids']/form//field[@name='%s'][@required='True']" % field)
    assert 'root_plan_id.name' in tariff_arch.xpath("//field[@name='cost_ids']")[0].get('domain')
    for kind in ('propio', 'contratista'):
        action = env.ref('step_cosecha.step_pricelist_action_' + kind + '_cosecha')
        assert (tariff_view.id, 'form') in action._get_action_dict()['views']
        rates = env['product.pricelist'].search([('cosecha', '=', True), ('group_type', '=', kind)], limit=5)
        rates.web_read({'name': {}, 'cost_ids': {'fields': {'display_name': {}}},
            'item_ids': {'fields': {'labor_id': {'fields': {'display_name': {}}},
                                   'uom_id': {'fields': {'display_name': {}}}, 'fixed_price': {}}}})
    if 'step_harvest_launcher' in EXPECTED:
        from odoo.addons.step_harvest_launcher.controllers.scope import environment_scope
        assert len(environment_scope(env)) == 64
        assert env.ref('step_harvest_launcher.menu_harvest_root').action == env.ref('step_harvest_launcher.action_open_harvest')
        assert env.ref('step_harvest_launcher.action_open_harvest').url == '/harvest/open'
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'tickets': [101, 102, 231, *([232] if 'step_harvest_launcher' in EXPECTED else [])], 'versions': EXPECTED,
          'native_masters': True, 'contractor_header': True, 'nested_fields_valid': True,
          'existing_records_web_read': True, 'harvest_tariff_menu_form': True,
          'harvest_tariff_native_labor_unit': True, 'harvest_tariff_center_scope': True,
          'harvest_own_form_without_studio': True,
          'harvest_api_context_scope': 'step_harvest_launcher' in EXPECTED}))
finally:
    env.cr.rollback()
