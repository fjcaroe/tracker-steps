"""Odoo shell probe; all created records and messages are rolled back."""
import importlib
import json

from lxml import etree
from odoo.tests import Form

try:
    for addon, expected in EXPECTED_ALL.items():
        installed = env['ir.module.module'].search([('name', '=', addon)])
        assert installed.state == 'installed' and installed.latest_version == expected
        assert importlib.import_module('odoo.addons.' + addon).__file__.startswith(ROOT + '/')
    assert env['step.dispatch.guide']._fields['freight_order_id'].comodel_name == 'step.freight.order'
    assert env['step.dispatch.guide']._fields['freight_route_id'].comodel_name == 'step.freight.route'
    module = env['ir.module.module'].search([('name', '=', 'step_operations_ui')])
    assert module.state == 'installed' and module.latest_version == EXPECTED
    assert importlib.import_module('odoo.addons.step_operations_ui').__file__.startswith(ROOT + '/')
    operator = env['res.users'].create({
        'name': 'Validación Fletes', 'login': 'qa_freight_probe_' + env.cr.dbname,
        'email': 'qa-freight-probe@example.invalid',
        'groups_id': [(6, 0, [env.ref('base.group_user').id])],
        'company_id': env.company.id, 'company_ids': [(6, 0, [env.company.id])],
    })
    checked = []
    masters = env.ref('step_operations_ui.menu_freight_masters')
    configuration = env.ref('step_operations_ui.menu_freight_configuration')
    assert masters.active and masters.parent_id == configuration.parent_id
    expected_menus = {
        'menu_freight_tariffs': 'tarifa_de_fletes_dcc8390a-9e92-4f69-b5cc-2dcb3e27bb2d',
        'menu_freight_carriers': 'transportistas_2c1977c3-a30e-4b17-b0f5-b339cac43c54',
        'menu_freight_trucks': 'camiones_1bffc703-8cbf-4682-a0a9-a351661d8620',
    }
    assert set(masters.child_id.ids) == {
        env.ref('step_operations_ui.' + name).id for name in expected_menus}
    for name, action in expected_menus.items():
        menu = env.ref('step_operations_ui.' + name)
        assert menu.active and menu.parent_id == masters
        assert menu.action == env.ref('step_operations_ui.' + action)
    checked.append({'masters_menu': masters.id, 'existing_actions_preserved': True})
    for model, prefix, action_id, menu_id in (
        ('step.freight.route', 'route', 'tramo_de_flete_0d34e499-bb52-47a3-a65e-9ac00a4c336e', 'menu_freight_routes'),
        ('step.freight.cold.mode', 'cold_mode', 'action_freight_cold_mode', 'menu_freight_cold_modes'),
    ):
        action = env.ref('step_operations_ui.' + action_id)
        menu = env.ref('step_operations_ui.' + menu_id)
        assert menu.active and menu.action == action
        form_id = dict((kind, view) for view, kind in action.views)['form']
        assert form_id == env.ref('step_operations_ui.view_freight_' + prefix + '_form').id
        user_model = env[model].with_user(operator)
        assert user_model.get_view(view_type='form')['id'] == form_id
        arch = etree.fromstring(user_model.get_view(view_id=form_id, view_type='form')['arch'])
        assert arch.xpath('//chatter')
        assert not env['ir.model.fields'].search([('model', '=', model), ('state', '=', 'manual')])
        data = env['ir.model.data'].search([('module', '=', 'studio_customization'), ('model', '=', 'ir.ui.view')])
        assert not env['ir.ui.view'].browse(data.mapped('res_id')).exists().filtered(
            lambda view: view.active and view.model == model)
        form = Form(user_model, view=env['ir.ui.view'].browse(form_id))
        form.name = 'Validación de ' + prefix
        if prefix == 'route':
            form.origin, form.destination = 'Origen validación', 'Destino validación'
            form.km_from, form.km_to = 19, 29
        else:
            form.code = '05'
        record = form.save()
        assert record.display_name == 'Validación de ' + prefix
        assert record._get_thread_with_access(record.id) == record
        assert record.message_post(body='Validación del historial', message_type='comment') in record.message_ids
        # Verify existing client records can open their threads too.
        for previous in user_model.search([('id', '!=', record.id)]):
            assert previous._get_thread_with_access(previous.id) == previous
        checked.append({'model': model, 'form_id': form_id, 'menu_id': menu.id, 'create_and_chatter': True})
    # Exercise the same nested read as web_save, including widget dependencies
    # on an empty Costeo tab; a successful create() did not detect T27's crash.
    orders = env['step.freight.order'].with_user(operator)
    order_view = env.ref('step_operations_ui.view_freight_order_code_form')
    order_action = env.ref('step_operations_ui.orden_de_flete_104802ff-cd72-4d5a-886e-66109a2b7833')
    assert dict((kind, view) for view, kind in order_action.views)['form'] == order_view.id
    form = Form(orders, view=order_view)
    form.description = 'Validación registro de fletes'
    order = form.save()
    assert order.name not in ('Nueva orden', '/')
    assert env.ref('step_operations_ui.sequence_freight_order').code == 'gastos.fletes'
    if 'base.automation' in env:
        assert not env['base.automation'].search([('model_name', '=', 'step.freight.order')]).filtered(
            lambda rule: any('gastos.fletes' in (action.code or '') for action in rule.action_server_ids))
    specification = {'name': {}, 'description': {}, 'freight_total': {},
        'detail_ids': {'fields': {name: {} for name in (
            'vehicle_id', 'driver_id', 'route_id', 'service_product_id',
            'cargo_description', 'delivery_reference', 'uom_id', 'quantity', 'unit_rate', 'freight_value')}},
        'cost_ids': {'fields': {name: {} for name in (
            'service_product_id', 'freight_cost', 'expense_account_id',
            'analytic_distribution', 'analytic_precision')}}}
    result = order.web_save({'description': 'Validación registro editado'}, specification)[0]
    assert result['description'] == 'Validación registro editado' and result['cost_ids'] == []
    assert order.web_read(specification)[0]['id'] == order.id
    for previous in orders.search([('id', '!=', order.id)]):
        assert previous.web_read(specification)[0]['id'] == previous.id
    checked.append({'model': 'step.freight.order', 'form_id': order_view.id,
                    'create_edit_reopen_web_save': True, 'internal_user': True})
    print('FREIGHT_REGISTRY_OK ' + json.dumps({'database': env.cr.dbname, 'version': EXPECTED, 'checks': checked}))
finally:
    env.cr.rollback()
