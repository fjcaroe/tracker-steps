"""T170 effective native monthly form and permitted holding contract selection."""
import importlib
import json
from pathlib import Path
from lxml import etree
from native_business_profile import scoped_business_environment

try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    scoped = scoped_business_environment(env)
    menu = scoped.ref('step_packing_operations.menu_packing_monthly_fruit_bill', raise_if_not_found=False)
    action = scoped.ref('step_packing_operations.action_monthly_fruit_bill')
    menus = scoped['ir.ui.menu'].search([('action', '=', 'ir.actions.act_window,%s' % action.id)])
    assert set(menus.ids) & scoped['ir.ui.menu']._visible_menu_ids()
    arch = etree.fromstring(scoped['step.packing.monthly.fruit.bill'].get_view(
        view_id=scoped.ref('step_packing_operations.view_monthly_fruit_bill').id, view_type='form')['arch'])
    assert arch.xpath("//field[@name='contract_id']")
    sample = env['step.packing.production'].search([('name', '=', 'OT/2026/00019')], limit=1)
    if sample:
        companies = sample.company_id.sudo().search([('id', 'parent_of', sample.company_id.id)])
        row = sample.with_context(allowed_company_ids=companies.ids)
        assert sample.company_id in row._contract_companies()
    if sample and env.cr.dbname.startswith(('MANAGEMENT_QA_CERRO_', 'MANAGEMENT_QA_QA-CERRO_')):
        branch = sample.company_id
        parent = branch.parent_id or branch
        account = env['account.account'].search([
            ('company_ids', 'in', branch.id), ('account_type', '=', 'expense')], limit=1)
        assert account
        source = sample.step_packing_output_tag_ids.filtered(
            lambda tag: tag.step_packing_result == 'export')
        assert source
        contract = env['step.producer.purchase.contract'].with_company(parent).create({
            'partner_id': sample.fruit_grower_id.id, 'company_id': parent.id})
        seen = set()
        for tag in source:
            for detail in tag.step_tag_line_ids:
                key = (detail.product_id.id, tag.especie_id.id)
                if key in seen:
                    continue
                seen.add(key)
                line = env['step.producer.purchase.contract.product'].create({
                    'contract_id': contract.id, 'product_id': detail.product_id.id,
                    'species_id': tag.especie_id.id, 'quantity': 1,
                    'uom_id': detail.product_id.uom_id.id, 'price_unit': 2,
                    'debit_account_id': account.id})
                env['step.producer.purchase.contract.installment'].create({
                    'contract_id': contract.id, 'product_line_id': line.id,
                    'quantity': 1, 'date_due': sample.date})
        contract.action_confirm()
        company_scope = (parent | branch).ids
        business = scoped_business_environment(env, company=branch)
        business = business(context=dict(business.context, allowed_company_ids=company_scope))
        wizard = business['step.packing.monthly.fruit.bill'].create({
            'company_id': branch.id, 'date_start': sample.date.replace(day=1),
            'date_end': sample.date, 'producer_ids': [(6, 0, sample.fruit_grower_id.ids)],
            'contract_id': contract.id})
        before = sample.read(['valuation_snapshot', 'state', 'contract_id'])[0]
        first = wizard.action_prepare_bills()
        bill = sample.purchase_bill_id
        assert bill and bill.state == 'draft' and bill.company_id == branch
        assert sample.read(['valuation_snapshot', 'state', 'contract_id'])[0] == before
        assert wizard.action_prepare_bills()['domain'] == first['domain']
        assert bill.invoice_line_ids and all(line.company_id == branch for line in bill.line_ids)
        print('T170_BRANCH_MONTHLY_FLOW_OK')
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({
        'ticket': 170, 'versions': EXPECTED, 'existing_profile': scoped.uid,
        'native_monthly_form': True, 'writes': False}))
finally:
    env.cr.rollback()
