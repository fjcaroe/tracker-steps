"""Read the native T212 screens and exercise the reported flow in a disposable copy."""
import json
from lxml import etree
from odoo.tools.safe_eval import safe_eval


def verify_shipment_dispatch(env, scoped):
    matrix = scoped.company
    dispatch_menu = scoped.ref('step_packing_dispatch.dispatch_menu')
    shipment_menu = scoped.ref('step_export.menu_step_export_shipping_instruction')
    visible = scoped['ir.ui.menu']._visible_menu_ids()
    assert dispatch_menu.id in visible and shipment_menu.id in visible
    guides = scoped[dispatch_menu.action.res_model]
    shipments = scoped[shipment_menu.action.res_model]
    guide_arch = etree.fromstring(guides.get_view(view_type='form')['arch'])
    shipment_arch = etree.fromstring(shipments.get_view(view_type='form')['arch'])
    field, = guide_arch.xpath("//field[@name='step_export_shipment_id']")
    assert "step_shipment_company_id" in field.get('context')
    assert shipment_arch.xpath("//field[@name='dispatch_guide_ids']/list/field[@name='company_id']")
    packing_arch = etree.fromstring(scoped['step.export.packing.list'].get_view(view_type='list')['arch'])
    assert packing_arch.xpath("//field[@name='step_dispatch_branch_id']")
    active = shipments.search_count([('company_id', '=', matrix.id), ('state', '=', 'validated')])
    assert scoped['step.freight.dispatch.type'].search_count([('step_recipient_kind', '=', 'shipment')])
    for kind in env['step.freight.dispatch.type'].search([('name', '=ilike', 'Embarque'),
            ('step_recipient_kind', '=', 'shipment')]):
        source = kind.company_id.root_id
        if kind.company_ids and kind.company_ids.root_id == source:
            holding = env['res.company'].search([('id', 'child_of', source.id)])
            assert not (holding - kind.company_ids), 'An existing dispatch type is missing an authorized branch'
    print('T212_REGISTRY_OK ' + json.dumps({'menu': True, 'guide_form': True,
        'branch_column_in_guides_and_packing_lists': True, 'validated_matrix_shipments': active}))
    if not env.cr.dbname.startswith('MANAGEMENT_QA_QA-CERRO_'):
        return
    # Use the existing draft in the customer's compatibility copy. Never assign it live.
    candidate = env[guides._name].search([('company_id', 'child_of', matrix.id),
        ('company_id', '!=', matrix.id), ('state', '=', 'draft'),
        ('dispatch_type_id.step_recipient_kind', '=', 'shipment'),
        ('step_export_shipment_ids', '=', False)], limit=1)
    if not candidate:
        return
    branch = scoped_business_environment(env, company=candidate.company_id)
    guide = candidate.with_env(branch)
    values = {'company_id': branch.company.id, 'step_recipient_kind': 'shipment',
              'step_shipment_company_id': guide.step_shipment_company_id.id}
    context = safe_eval(field.get('context'), values)
    domain = safe_eval(field.get('domain'), values)
    assert context == {'allowed_company_ids': matrix.ids}
    candidates = branch[shipments._name].with_context(**context).name_search(args=domain)
    assert candidates, 'The validated matrix shipment is missing from the guide selector'
    shipment = scoped[shipments._name].browse(candidates[0][0])
    assert shipment.state == 'validated' and shipment.company_id == matrix
    recipients = branch['res.partner'].search(guide.step_recipient_domain)
    partner = shipment.receiver_id.with_env(branch) & recipients
    partner = partner or recipients[:1]
    assert partner
    spec = {'step_export_shipment_id': {'fields': {'display_name': {}}}}
    try:
        saved, = guide.web_save({'partner_id': partner.id, 'step_export_shipment_id': shipment.id}, spec)
        assert saved['step_export_shipment_id']['id'] == shipment.id
        linked = shipment.with_context(allowed_company_ids=(matrix | branch.company).ids)
        rows, = linked.web_read({'dispatch_guide_ids': {
            'order': 'date desc,id desc', 'fields': {'company_id': {'fields': {'display_name': {}}}}}})
        assert any(row['id'] == guide.id and row['company_id']['id'] == branch.company.id
                   for row in rows['dispatch_guide_ids'])
        assert guide.company_id == branch.company and branch.companies == branch.company
        print('T212_CUSTOMER_COPY_OK ' + json.dumps({'validated_matrix_selector': True,
            'draft_saved': True, 'branch_visible_in_matrix': True}))
    finally:
        env.cr.rollback()


verify_shipment_dispatch(env, scoped)


def verify_branch_packing_list(env, scoped):
    menu = scoped.ref('step_packing_operations.menu_packing_dispatch_packing_list')
    assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
    model = scoped[menu.action.res_model]
    arch = etree.fromstring(model.get_view(view_type='form')['arch'])
    shipment_field, = arch.xpath("//field[@name='shipment_id']")
    guide_field, = arch.xpath("//field[@name='guide_id']")
    shipment_domain = shipment_field.get('domain')
    for is_branch, company_id, expected in (
            (False, scoped.company.id, []), (True, False, [('id', '=', False)]),
            (True, scoped.company.id, [('company_id', '=', scoped.company.id), ('state', '!=', 'draft')])):
        assert safe_eval(shipment_domain, {'step_packing_is_branch': is_branch,
            'step_packing_matrix_id': company_id}) == expected
    assert safe_eval(guide_field.get('context'), {'step_packing_company_ids': [], 'context': {
        'allowed_company_ids': scoped.company.ids}}) == {'allowed_company_ids': scoped.company.ids}
    matrix_arch = etree.fromstring(scoped['step.export.export'].get_view(view_type='form')['arch'])
    assert matrix_arch.xpath("//field[@name='packing_list_ids']/list/field[@name='step_dispatch_branch_id']")
    code = 'step.export.packing.list'
    assert env['ir.sequence'].search_count([('code', '=', code), ('company_id', 'in', [False, scoped.company.id])])
    print('T213_REGISTRY_OK ' + json.dumps({'packing_menu': True, 'branch_form': True, 'matrix_tab': True, 'sequence': True}))
    if not env.cr.dbname.startswith('MANAGEMENT_QA_QA-CERRO_'):
        return
    guide = env['step.dispatch.guide'].search([('external_folio', '=', '6666'),
        ('step_recipient_kind', '=', 'shipment'), ('state', '=', 'confirmed')], limit=1)
    if not guide:
        return
    branch = scoped_business_environment(env, company=guide.company_id)
    shipment = guide.step_export_shipment_ids.filtered(lambda row: row.name == 'M0260')
    assert len(shipment) == 1 and len(guide.load_tag_ids) == 3
    packing_model = branch[model._name]
    draft = packing_model.new({'shipment_id': shipment.id, 'guide_id': guide.id})
    context = safe_eval(shipment_field.get('context'), {'step_packing_company_ids': draft.step_packing_company_ids.ids})
    domain = safe_eval(shipment_domain, {'step_packing_is_branch': draft.step_packing_is_branch,
        'step_packing_matrix_id': draft.step_packing_matrix_id.id})
    choices = branch[shipment._name].with_context(**context).name_search('M0260', args=domain)
    assert shipment.id in {row[0] for row in choices}
    choices = branch[guide._name].name_search('6666', args=[('id', 'in', draft.available_guide_ids.ids)])
    assert guide.id in {row[0] for row in choices}
    try:
        expected = guide.load_tag_ids
        spec = {'name': {}, 'shipment_id': {'fields': {'display_name': {}}}, 'box_qty': {}, 'kg_qty': {},
                'tag_ids': {'fields': {'name': {}}, 'order': 'name,id'}}
        draft._onchange_guide_tags()
        assert draft.tag_ids.ids == expected.ids
        saved, = packing_model.web_save({'shipment_id': shipment.id, 'guide_id': guide.id}, spec)
        assert saved['name'].startswith('PL/') and saved['shipment_id']['id'] == shipment.id
        assert {row['id'] for row in saved['tag_ids']} == set(expected.ids)
        assert saved['box_qty'] == sum(expected.mapped('box_count')) == 720
        assert saved['kg_qty'] > 0
        parent = scoped['step.export.export'].with_context(allowed_company_ids=context['allowed_company_ids'])
        reflected, = parent.browse(shipment.id).web_read({'packing_list_ids': {'order': 'date desc,id desc',
            'fields': {'step_dispatch_branch_id': {'fields': {'display_name': {}}}}}})
        assert any(row['id'] == saved['id'] and row['step_dispatch_branch_id']['id'] == branch.company.id
                   for row in reflected['packing_list_ids'])
        assert packing_model.browse(saved['id']).action_export_excel()['type'] == 'ir.actions.act_url'
        print('T213_CUSTOMER_COPY_OK ' + json.dumps({'shipment': 'M0260', 'guide': '6666', 'tags': 3,
            'boxes': saved['box_qty'], 'net_kg': saved['kg_qty'], 'visible_in_matrix': True, 'excel': True}))
    finally:
        env.cr.rollback()


if 'step_uses_guide_pallets' in env['step.export.packing.list']._fields:
    verify_branch_packing_list(env, scoped)
