"""Roll back a complete correction under an existing editor in the receipt's branch."""
import json
from odoo.addons.step_packing_producer_change.tests.test_receipt_producer import ReceiptProducerCase

try:
    source = env['stock.picking'].search([('step_fruit_reception_kind', '=', 'process'),
        ('state', '=', 'done'), ('fruit_tag_line_ids.package_id.step_tag_state', '=', 'validated')],
        order='id desc', limit=1)
    assert source, 'Review an existing native receiving branch'
    company = source.company_id
    administrative = env(context=dict(env.context, allowed_company_ids=company.ids,
        tracking_disable=True, no_reset_password=True, mail_create_nosubscribe=True))
    candidates = administrative['res.users'].search([('active', '=', True), ('share', '=', False),
        ('id', '!=', 1), ('company_ids', 'in', company.ids)])
    for user in candidates.filtered(lambda u: u.has_group('stock.group_stock_manager')):
        business = administrative(user=user, su=False)
        try:
            business['stock.picking'].browse(source.id)._step_check_received_producer_access()
        except Exception:
            continue
        break
    else:
        raise AssertionError('No existing authorized receiving editor')
    case = ReceiptProducerCase('test_received_producer_stock_history_and_repeat')
    case.env, case.cr = administrative, env.cr
    case.wh = administrative['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
    case.producer = administrative['res.partner'].create({'name': 'QA246 propietario inicial', 'is_productor': True})
    case.fundo = administrative['step.fundo'].create({'name': 'QA246 origen', 'partner_id': case.producer.id, 'company_id': company.id})
    case.species = administrative['step.especie'].create({'name': 'QA246 especie', 'type_especie': 'frutal', 'group_especie': 'fruta_h'})
    kg = administrative.ref('uom.product_uom_kgm')
    case.product = administrative['product.product'].create({'name': 'QA246 fruta kg', 'is_storable': True,
        'uom_id': kg.id, 'uom_po_id': kg.id})
    case.packaging = administrative['product.packaging'].create({'name': 'QA246 envase', 'product_id': case.product.id, 'qty': 8})
    case.prepare()
    before, original = case.snapshot(), case.received.move_ids
    action = case.tags[0].with_env(business).action_step_change_received_producer()
    wizard = business[action['res_model']].with_context(action['context']).create({
        'producer_id': case.other.id, 'reason': 'Prueba integral de usuario existente QA246'})
    assert not wizard.env.su
    wizard.action_apply()
    assert case.snapshot() == before and case.received.move_ids == original
    assert case.received.partner_id == case.other and case.tags.owner_id == case.other
    assert case.tags.step_producer_id == case.other and case.tags.step_tag_line_ids.producer_id == case.other
    assert case.received.step_producer_change_move_ids.create_uid == user
    assert not case.received.step_producer_change_move_ids.picking_id
    print('T246_EXISTING_BUSINESS_FLOW_OK ' + json.dumps({'database': env.cr.dbname,
        'company_id': company.id, 'user_id': user.id, 'superuser': False,
        'native_receipt_and_tags': True, 'original_records_preserved': True, 'rolled_back': True}))
finally:
    env.cr.rollback()
