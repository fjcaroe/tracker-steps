"""Odoo shell probe; all created records and messages are rolled back."""
import importlib
import json

from lxml import etree
from odoo.tests import Form

try:
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
    for model, prefix, action_id, menu_id in (
        ('x_tramo_de_flete', 'route', 'tramo_de_flete_0d34e499-bb52-47a3-a65e-9ac00a4c336e', 'menu_freight_routes'),
        ('x_modalidad_de_frio', 'cold_mode', 'action_freight_cold_mode', 'menu_freight_cold_modes'),
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
        form.x_name = 'Validación de ' + prefix
        if prefix == 'route':
            form.origin, form.destination = 'Origen validación', 'Destino validación'
            form.x_studio_km_desde, form.x_studio_km_hasta = 19, 29
        else:
            form.x_studio_cdigo = '05'
        record = form.save()
        assert record.display_name == 'Validación de ' + prefix
        assert record._get_thread_with_access(record.id) == record
        assert record.message_post(body='Validación del historial', message_type='comment') in record.message_ids
        # Verify existing client records can open their threads too.
        for previous in user_model.search([('id', '!=', record.id)]):
            assert previous._get_thread_with_access(previous.id) == previous
        checked.append({'model': model, 'form_id': form_id, 'menu_id': menu.id, 'create_and_chatter': True})
    print('FREIGHT_REGISTRY_OK ' + json.dumps({'database': env.cr.dbname, 'version': EXPECTED, 'checks': checked}))
finally:
    env.cr.rollback()
