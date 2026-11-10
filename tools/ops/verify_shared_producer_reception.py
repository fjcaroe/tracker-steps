"""T194: read the native menu and exercise the private Cerro case in a clone only."""
from lxml import etree
from odoo.tools.safe_eval import safe_eval


def verify_shared_producer_reception(env, reviewer, case):
    native = env.ref('base.res_partner_rule')
    read = env.ref('step_agriculture_multicompany.partner_company_read')
    assert native.active and native['global'] and not native.perm_read
    assert native.perm_write and native.perm_create and native.perm_unlink
    assert read.active and read['global'] and read.perm_read
    assert not (read.perm_write or read.perm_create or read.perm_unlink)
    action = env.ref('step_inventory_packing.action_steps_fruit_process_reception')
    menu = env.ref('step_inventory_packing.menu_steps_fruit_process_reception')
    assert menu.action == action and action.res_model == 'stock.picking'
    form_id = dict((kind, view) for view, kind in action.views)['form']
    result = {'native_menu_and_form': True, 'case': None}
    context = dict(safe_eval(action.context), mail_notrack=True, tracking_disable=True,
                   mail_create_nosubscribe=True, mail_notify_force_send=False)
    if case:
        assert env.cr.dbname == 'CERRO_EL_PLOMO' or env.cr.dbname.startswith('MANAGEMENT_QA_CERRO_')
        reviewer = env(user=case['user_id'], context={**context, 'allowed_company_ids': [case['company_id']]})
    assert menu.id in reviewer['ir.ui.menu']._visible_menu_ids()
    picking_model = reviewer['stock.picking']
    arch = etree.fromstring(picking_model.get_view(view_id=form_id, view_type='form')['arch'])
    assert arch.xpath("//field[@name='partner_id']") and arch.xpath("//field[@name='fruit_fundo_id']")
    assert arch.xpath("//button[@name='button_validate']")
    if not case:
        return result

    receipt = picking_model.browse(case['receipt_id'])
    assert picking_model.search_count([('id', '=', receipt.id), *safe_eval(action.domain)]) == 1
    assert receipt.company_id.id == case['company_id']
    assert receipt.fruit_fundo_id.id == case['farm_id'] and receipt.partner_id.id == case['producer_id']
    assert receipt.partner_id == receipt.fruit_fundo_id.partner_id
    assert receipt.company_id in receipt.fruit_fundo_id.company_ids
    assert receipt.company_id != receipt.partner_id.sudo().company_id
    assert receipt.partner_id.read(['name']) and not receipt.partner_id.has_access('write')
    data = receipt.web_read({'state': {}, 'fruit_fundo_id': {'fields': {'display_name': {}}},
                             'partner_id': {'fields': {'display_name': {}}}})[0]
    assert data['fruit_fundo_id']['id'] == case['farm_id'] and data['partner_id']['id'] == case['producer_id']
    receipt._check_company()
    state_before = receipt.state
    result['case'] = {'contact_read': True, 'stock_company_check': True, 'state_before': state_before}
    if env.cr.dbname.startswith('MANAGEMENT_QA_CERRO_'):
        assert state_before in ('draft', 'confirmed', 'assigned')
        expected = sum(move.product_uom._compute_quantity(move.quantity, move.product_id.uom_id, round=False)
                       for move in receipt.move_ids)
        assert expected > 0
        reply = receipt.button_validate()
        if isinstance(reply, dict) and reply.get('res_model') == 'stock.backorder.confirmation':
            wizard = reviewer['stock.backorder.confirmation'].with_context(reply.get('context', {})).create({})
            wizard.process()
        assert receipt.state == 'done', 'The native validation did not finish'
        packages = receipt.fruit_tag_line_ids.package_id
        assert packages and set(packages.mapped('step_tag_state')) == {'validated'}
        assert packages.step_process_reception_id == receipt
        assert packages.quant_ids.company_id == receipt.company_id
        assert packages.quant_ids.owner_id == receipt.partner_id
        assert abs(sum(packages.quant_ids.mapped('quantity')) - expected) < 0.00001
        result['case'].update(validated_in_copy=True, tags=len(packages), owner_preserved=True)
    return result
