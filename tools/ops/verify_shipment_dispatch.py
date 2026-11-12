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
