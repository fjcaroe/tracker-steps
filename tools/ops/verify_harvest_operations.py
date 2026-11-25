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
    for field in ('product_tmpl_id', 'uom_id'):
        assert tariff_arch.xpath("//field[@name='item_ids']/list/field[@name='%s']" % field)
        assert tariff_arch.xpath("//field[@name='item_ids']/form//field[@name='%s'][@required]" % field)
    assert 'root_plan_id.name' in tariff_arch.xpath("//field[@name='cost_ids']")[0].get('domain')
    for kind in ('propio', 'contratista'):
        action = env.ref('step_cosecha.step_pricelist_action_' + kind + '_cosecha')
        assert action._get_action_dict()['views'][0] == (False, 'list')
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
    dashboard = 'harvest_hours_per_day' in env['res.company']._fields
    if dashboard:
        data = env['step.cosecha.registry'].get_dashboard_data()
        assert data['period'] == 'today' and 0 < data['hours_per_day'] <= 24
        assert all(key in data for key in ('species', 'farms', 'offset', 'limit', 'recent'))
        for row in data['recent']:
            assert all(key in row for key in ('workers', 'hours', 'average_kg', 'total_cost', 'cost_per_kg', 'species'))
        settings = env.ref('step_cosecha_operations.harvest_dashboard_settings')
        arch = etree.fromstring(env['res.config.settings'].get_view(view_id=settings.id, view_type='form')['arch'])
        assert arch.xpath(".//field[@name='harvest_hours_per_day']")
        assert env.ref('step_cosecha_operations.menu_harvest_dashboard_settings').action
    costing = 'harvest_unit_price' in env['step.cosecha.registry.line']._fields
    if costing:
        arch = etree.fromstring(env['step.cosecha.registry'].get_view(
            view_id=env.ref('step_cosecha.view_step_cosecha_registry_form').id, view_type='form')['arch'])
        assert arch.xpath("//header/button[@name='action_return_approved']")
        for name in ('harvest_min_quantity', 'harvest_unit_price', 'harvest_salary_base'):
            assert arch.xpath("//page[@name='movi_line']//field[@name='%s']" % name)
        for kind in ('pro', 'contratista'):
            action = env.ref('step_cosecha.action_step_cosecha_costo_pro' if kind == 'pro'
                else 'step_cosecha.action_step_cosecha_registry_costo')
            assert action.res_model == 'step.cosecha.registry'
        existing = env['step.cosecha.registry'].search([('company_id', '=', env.company.id)], limit=8)
        existing.web_read({'name': {}, 'state': {}, 'registry_line': {'fields': {
            'harvest_min_quantity': {}, 'harvest_unit_price': {}, 'harvest_salary_base': {},
            'total_trato': {}, 'variable_trato': {}, 'cost_empresa': {}}}})
    lifecycle = 'mobile_state_date' in env['step.cosecha.registry']._fields
    crew_attendance = 'harvest_crew_id' in env['hr.attendance']._fields if 'hr.attendance' in env else False
    if lifecycle:
        arch = etree.fromstring(env['step.cosecha.registry'].get_view(
            view_id=env.ref('step_cosecha.view_step_cosecha_registry_form').id, view_type='form')['arch'])
        for field in ('mobile_status', 'mobile_state_date', 'mobile_state_user_id'):
            assert arch.xpath(".//field[@name='%s']" % field), field
    if crew_attendance:
        for kind, parent in (('own', 'menu_step_cosecha_main'), ('contractor', 'menu_step_cosecha_main_contra')):
            menu = env.ref('step_harvest_launcher.menu_harvest_attendance_' + kind)
            assert menu.active and menu.parent_id == env.ref('step_cosecha.' + parent)
            assert menu.action == env.ref('step_harvest_launcher.harvest_attendance_' + kind)
            assert menu.action.res_model == 'hr.attendance'
            assert menu.action._get_action_dict()['views'][0] == (
                env.ref('step_harvest_launcher.harvest_attendance_list').id, 'list')
        for kind in ('list', 'form'):
            view = env.ref('step_harvest_launcher.harvest_attendance_' + kind)
            arch = etree.fromstring(env['hr.attendance'].get_view(view_id=view.id, view_type=kind)['arch'])
            check_fields('hr.attendance', arch)
            for field in ('employee_id', 'harvest_crew_id', 'check_in', 'check_out', 'worked_hours'):
                assert arch.xpath(".//field[@name='%s']" % field), field
        env['hr.attendance'].search([('harvest_crew_id.company_id', '=', env.company.id)], limit=8).web_read({
            'employee_id': {'fields': {'display_name': {}}}, 'harvest_crew_id': {'fields': {'display_name': {}}},
            'check_in': {}, 'check_out': {}, 'worked_hours': {}})
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'tickets': [101, 102, 231, *([232] if 'step_harvest_launcher' in EXPECTED else []), *([234] if dashboard else []), *([235] if costing else []), *([236] if lifecycle else []), *([237] if crew_attendance else [])], 'versions': EXPECTED,
          'native_masters': True, 'contractor_header': True, 'nested_fields_valid': True,
          'existing_records_web_read': True, 'harvest_tariff_menu_form': True,
          'harvest_tariff_native_labor_unit': True, 'harvest_tariff_center_scope': True,
          'harvest_own_form_without_studio': True,
          'harvest_api_context_scope': 'step_harvest_launcher' in EXPECTED,
          'harvest_dashboard_native_filters_table_settings': dashboard,
          'harvest_costing_native_rate_and_return': costing,
          'harvest_mobile_lifecycle_form': lifecycle,
          'harvest_crew_attendance_menu_form': crew_attendance}))
finally:
    env.cr.rollback()
