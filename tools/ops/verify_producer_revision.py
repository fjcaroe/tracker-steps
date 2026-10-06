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
        if menu == env.ref('step_export.menu_producer_packaging_materials'):
            result = action.run()
            assert result['domain'] == env['mrp.bom']._packaging_material_domain()
            env['product.product'].search(result['domain'], limit=1)
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
    assert env.ref('step_producer_fruit_flow.menu_producer_packing_tags').action == env.ref('step_producers_integrations.action_producer_packing_control')
    assert env.ref('step_producer_fruit_flow.menu_producer_shipments').action == env.ref('step_producers_integrations.action_producer_shipment_control')
    for view in ('view_producer_packing_control', 'view_producer_shipment_control'):
        tree = etree.fromstring(env['step.fruit.package.line'].get_view(
            view_id=env.ref('step_producers_integrations.' + view).id, view_type='list')['arch'].encode())
        assert tree.get('create') == tree.get('edit') == tree.get('delete') == '0'
    bom_tree = etree.fromstring(env['mrp.bom'].get_view(
        view_id=env.ref('step_export.view_export_fruit_bom_form').id, view_type='form')['arch'].encode())
    assert 'step_export_packaging_category_id' in bom_tree.xpath("//field[@name='bom_line_ids']//field[@name='product_id']")[0].get('domain')
    # The completed QA walkthrough exercises the full source flows, not fake report rows.
    if env['ir.config_parameter'].get_param('steps.qa.productores.walkthrough.v1'):
        producer = env['res.partner'].search([('name','=','PRUEBA - Agrícola Valle Claro')])
        assert len(producer) == 1
        rows = env['step.fruit.package.line'].search([
            ('producer_id','=',producer.id),('package_id.name','in',['PRUEBA/EMBALADA/01','PRUEBA/EMBALADA/02'])])
        assert len(rows) == 2 and sum(rows.mapped('kilos')) == 800
        assert sum(rows.mapped('control_pending_kg')) == 400
        shipped = rows.filtered(lambda row: bool(row.control_shipment_ids))
        assert len(shipped) == 1 and shipped.control_tag_state == 'liquidated'
        assert abs(shipped.control_fob_usd - 2170) < 0.01
        assert abs(shipped.control_fob_unit_usd - 5.425) < 0.0001
        assert shipped.control_settlement_ids.name == 'PRUEBA/LIQ/01'
    estimate_arch = env['step.export.estimate'].get_view(view_type='form')['arch']
    estimate_tree = etree.fromstring(estimate_arch.encode())
    assert len(estimate_tree.xpath("//group[@name='estimate_header']/group")) == 2
    assert not estimate_tree.xpath("//field[@name='date_start'] | //field[@name='date_stop'] | //field[@name='export_kg_total'] | //field[@name='stage_id']")
    assert len(estimate_tree.xpath("//group[@name='estimate_header']//field[@name='fundo_id'] | //group[@name='estimate_header']//field[@name='season_id']")) == 2
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'versions': EXPECTED, 'menus': checked}, ensure_ascii=False))
finally:
    env.cr.rollback()
