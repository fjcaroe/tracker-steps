"""Read-only effective menu/action/form audit, run inside an Odoo shell."""
import importlib
import json
from odoo.tools.safe_eval import safe_eval
from verify_export_sale import verify_export_sale

try:
    module = env['ir.module.module'].search([('name', '=', 'step_export')])
    assert module.latest_version == EXPECTED['step_export']
    assert importlib.import_module('odoo.addons.step_export').__file__.startswith(ROOT + '/')
    root = env.ref('step_export.menu_step_export_root')
    children = env['ir.ui.menu'].search([('parent_id', '=', root.id)], order='sequence,id')
    assert children.with_context(lang='es_CL').mapped('name') == [
        'Inicio', 'Planificación', 'Embarque', 'Recibidor', 'Gastos exportación', 'Maestros', 'Configuraciones']
    technical = env.ref('step_export.menu_step_export_config_technical')
    menus = env['ir.ui.menu'].search([('id', 'child_of', root.id)])
    checked = []
    for menu in menus:
        if menu == technical or menu.parent_id == technical:
            assert env.ref('base.group_no_one') in menu.groups_id
            continue
        assert '(etiqueta)' not in menu.name and '(etapa)' not in menu.name
        action = menu.action
        if action and action._name == 'ir.actions.act_window':
            model = env[action.res_model]
            domain = safe_eval(action.domain or '[]', {'uid': env.uid, 'context': env.context})
            model.search(domain, limit=1)
            for mode in ('list', 'form'):
                if mode in action.view_mode.split(','):
                    view_id = action.view_id.id if action.view_id.type == mode else False
                    model.get_view(view_id=view_id, view_type=mode)
            checked.append(menu.complete_name)
    instruction = env.ref('step_export.action_export_shipping_instructions')
    assert instruction.res_model == 'step.export.export'
    arch = env['step.export.export'].get_view(view_type='form')['arch']
    for name in ('action_validate_shipment', 'sales_program_id', 'line_ids', 'vessel_id', 'consignee_id'):
        assert 'name="' + name + '"' in arch, name
    flow = verify_export_sale(env)
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'version': module.latest_version, 'menus': checked, 'sale_flow': flow}, ensure_ascii=False))
finally:
    env.cr.rollback()
