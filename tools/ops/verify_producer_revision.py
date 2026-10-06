"""Read-only effective producer menu and contract view probe, inside Odoo shell."""
import importlib
import json
from lxml import etree
from odoo.tools.safe_eval import safe_eval

try:
    for name, version in EXPECTED.items():
        assert env['ir.module.module'].search([('name', '=', name)]).latest_version == version, name
        assert importlib.import_module('odoo.addons.' + name).__file__.startswith(ROOT + '/'), name
    root = env.ref('step_producers.menu_step_producers_root')
    children = env['ir.ui.menu'].search([('parent_id', '=', root.id)], order='sequence,id')
    assert children.with_context(lang='es_CL').mapped('name') == [
        'Inicio', 'Planificación', 'Control Contratos', 'Control fruta', 'Liquidación', 'Maestros', 'Configuraciones']
    checked = []
    for menu in env['ir.ui.menu'].search([('id', 'child_of', root.id)]):
        action = menu.action
        if menu == env.ref('step_producers.menu_producer_accounting'):
            result = action.run()
            assert result['res_id'] == env.company.id
            assert result['views'] == [(env.ref('step_producers.view_producer_accounting_form').id, 'form')]
            env['res.company'].get_view(view_id=result['views'][0][0], view_type='form')
            checked.append(menu.complete_name)
        if action and action._name == 'ir.actions.act_window':
            model = env[action.res_model]
            variables = {'uid': env.uid, 'context': env.context, 'allowed_company_ids': env.companies.ids}
            model.search(safe_eval(action.domain or '[]', variables), limit=1)
            for mode in action.view_mode.split(','):
                if mode in ('list', 'form', 'kanban'):
                    view_id = action.view_id.id if action.view_id.type == mode else False
                    model.get_view(view_id=view_id, view_type=mode)
            checked.append(menu.complete_name)
    contract = env['step.producer.purchase.contract']
    arch = contract.get_view(view_id=env.ref('step_producers.view_step_producer_purchase_contract_form').id, view_type='form')['arch']
    tree = etree.fromstring(arch.encode())
    assert not tree.xpath("//field[@name='analytic_distribution'] | //field[@name='debit_account_id']")
    assert tree.xpath("//field[@name='advance_description']")
    assert 'step_export_enabled' in str(env['step.producer.purchase.contract.product']._fields['product_id'].domain)
    for line in env['step.producer.purchase.contract.product'].search([]):
        assert not line.display_name.startswith('step.producer.purchase.contract.product,'), line.id
    assert env.ref('step_producer_fruit_flow.menu_producer_packing_tags').action == env.ref('step_packing_operations.action_packing_production')
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'versions': EXPECTED, 'menus': checked}, ensure_ascii=False))
finally:
    env.cr.rollback()
