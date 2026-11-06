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
    if env.cr.dbname.startswith('MANAGEMENT_QA_CERRO_') and tuple(map(int, EXPECTED['step_packing_operations'].split('.'))) >= (18,0,2,12,0):
        assert MONTHLY_FRUIT_PLAN, 'Do not substitute the customer case with a synthetic contract'
        from verify_monthly_fruit_case import verify_case
        print('T170_ACTUAL_MONTHLY_CASE_OK ' + json.dumps(verify_case(env, MONTHLY_FRUIT_PLAN)))
    elif sample and env.cr.dbname.startswith(('MANAGEMENT_QA_CERRO_', 'MANAGEMENT_QA_QA-CERRO_')):
        # Customer QA has no closed operations. Represent a legacy closed
        # record only inside this rollback-only copy fixture.
        if sample.state not in ('closed', 'costed', 'accounted'):
            from odoo.addons.step_packing_operations.models.process_control import _INTERNAL
            sample.with_context(_packing_control=_INTERNAL).write({'state': 'closed'})
        branch = sample.company_id
        parent = branch.parent_id or branch
        if not branch.step_packing_purchase_journal_id:
            journal = env['account.journal'].search([
                ('company_id', '=', branch.id), ('type', '=', 'purchase')], limit=1)
            assert journal, 'The copy fixture requires an existing purchase journal'
            branch.step_packing_purchase_journal_id = journal
        account = env['account.account'].search([
            ('company_ids', 'in', (parent | branch).ids), ('account_type', '=', 'expense')], limit=1)
        assert account
        source = sample.step_packing_output_tag_ids.filtered(
            lambda tag: tag.step_packing_result == 'export')
        assert source
        contract = env['step.producer.purchase.contract'].with_company(parent).create({
            'partner_id': sample.fruit_grower_id.id, 'company_id': parent.id})
        seen = set()
        for tag in source:
            for detail in tag.step_tag_line_ids:
                base = detail.product_id.product_tmpl_id.step_export_base_product_id
                priced = base.product_variant_ids if base else detail.product_id
                key = (priced.id, tag.especie_id.id)
                if key in seen:
                    continue
                seen.add(key)
                line = env['step.producer.purchase.contract.product'].create({
                    'contract_id': contract.id, 'product_id': priced.id,
                    'species_id': tag.especie_id.id, 'quantity': 1,
                    'uom_id': priced.uom_id.id, 'price_unit': 2,
                    'debit_account_id': account.id})
                env['step.producer.purchase.contract.installment'].create({
                    'contract_id': contract.id, 'product_line_id': line.id,
                    'quantity': 1, 'date_due': sample.date})
        contract.action_confirm()
        company_scope = branch.ids
        business = scoped_business_environment(env, company=branch)
        business = business(context=dict(business.context, allowed_company_ids=company_scope))
        wizard = business['step.packing.monthly.fruit.bill'].create({
            'company_id': branch.id, 'date_start': sample.date.replace(day=1),
            'date_end': sample.date, 'producer_ids': [(6, 0, sample.fruit_grower_id.ids)],
            'contract_id': contract.id})
        before = sample.read(['valuation_snapshot', 'state', 'contract_id'])[0]
        assert wizard.env.companies == branch
        contract.with_env(business).check_access('read')
        from odoo.exceptions import UserError
        lines = contract.product_line_ids
        lines.write({'debit_account_id': False})
        for product in lines.product_id.with_company(branch):
            product.property_account_expense_id = False
            product.categ_id.property_account_expense_categ_id = False
        try:
            wizard.action_prepare_bills()
        except UserError as error:
            assert contract.display_name in str(error)
            assert all(line.product_id.display_name in str(error) for line in lines)
            assert not sample.purchase_bill_id
            print('T170_MISSING_ACCOUNTS_IDENTIFIED')
        else:
            raise AssertionError('Missing debit accounts must prevent invoice creation')
        lines.product_id.with_company(branch).write({'property_account_expense_id': account.id})
        first = wizard.action_prepare_bills()
        bill = sample.purchase_bill_id
        assert bill and bill.state == 'draft' and bill.company_id == branch
        assert sample.read(['valuation_snapshot', 'state', 'contract_id'])[0] == before
        assert wizard.action_prepare_bills()['domain'] == first['domain']
        assert bill.invoice_line_ids and all(line.company_id == branch for line in bill.line_ids)
        print('T170_NATIVE_EXPENSE_FLOW_OK BRANCH_ONLY_BASE_PRODUCT')
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({
        'ticket': 170, 'versions': EXPECTED, 'existing_profile': scoped.uid,
        'native_monthly_form': True, 'writes': False}))
finally:
    env.cr.rollback()
