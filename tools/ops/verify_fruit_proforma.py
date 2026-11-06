"""T171 effective UI and rollback-only native monthly proforma smoke proof.

The publisher supplies env, ROOT, EXPECTED and OUTPUT. Production validation is
read-only. The complete 33/46 cycle runs only in a disposable MANAGEMENT_QA copy;
its temporary companies, users and documents are always rolled back.
"""
import importlib
import json
from pathlib import Path

from lxml import etree

from native_business_profile import scoped_business_environment


def verify_ui(business):
    """Check the menu action and effective views, not only the module XML."""
    ref = business.ref
    billing = ref('step_packing_fruit_proforma.fruit_billing_menu')
    monthly = ref('step_packing_operations.menu_packing_monthly_purchase')
    proformas = ref('step_packing_fruit_proforma.fruit_proforma_menu')
    dispatch = ref('step_packing_operations.menu_packing_operations_dispatch')
    assert monthly.parent_id == billing and proformas.parent_id == billing
    assert billing.parent_id == dispatch.parent_id and dispatch.sequence < billing.sequence
    visible = business['ir.ui.menu']._visible_menu_ids()
    assert {billing.id, monthly.id, proformas.id}.issubset(visible)
    action = ref('step_packing_fruit_proforma.fruit_proforma_action')
    assert proformas.action == action and action.res_model == 'purchase.order'
    assert "step_fruit_proforma" in action.domain
    form_id = ref('step_packing_fruit_proforma.fruit_proforma_form').id
    arch = etree.fromstring(business['purchase.order'].get_view(
        view_id=form_id, view_type='form')['arch'])
    assert arch.get('create') == '0' and arch.get('duplicate') == '0'
    for button in ('action_fruit_approve', 'action_fruit_convert', 'button_cancel'):
        assert arch.xpath("//button[@name=%s]" % repr(button))
    assert not arch.xpath("//button[@name='button_confirm' or @name='button_draft']")
    for field in ('step_fruit_dte_code', 'step_fruit_withholding_tax_id',
                  'step_fruit_supplier_document_number', 'step_fruit_tag_ids',
                  'step_fruit_guide_refs', 'step_fruit_production_ids'):
        assert arch.xpath("//field[@name=%s]" % repr(field))
    monthly_arch = etree.fromstring(business['step.packing.monthly.fruit.bill'].get_view(
        view_id=ref('step_packing_operations.view_monthly_fruit_bill').id,
        view_type='form')['arch'])
    assert monthly_arch.xpath("//field[@name='contract_id']")
    assert monthly_arch.xpath("//button[@name='action_prepare_bills' and @string='Preparar proformas']")
    species_arch = etree.fromstring(business['step.especie'].get_view(
        view_id=ref('step_hr.view_step_especie_form').id, view_type='form')['arch'])
    assert species_arch.xpath("//field[@name='step_change_subject_vat']")
    assert species_arch.xpath("//field[@name='step_withholding_tax_id']")
    tag_arch = etree.fromstring(business['stock.quant.package'].get_view(
        view_id=ref('step_inventory_packing.view_quant_package_form_steps_fruit').id,
        view_type='form')['arch'])
    assert tag_arch.xpath("//field[@name='step_fruit_proforma_id']")
    for report_id in ('action_report_fruit_proforma', 'action_report_fruit_proforma_preview'):
        report = ref('step_packing_fruit_proforma.' + report_id)
        assert report.model == 'purchase.order'
        assert report.report_name == 'step_packing_fruit_proforma.report_fruit_proforma'
    return {'menus': True, 'monthly_form': True, 'proforma_form': True,
            'species_retention_selector': True, 'tag_proforma_link': True}


def verify_copy_cycle(admin, output):
    """Exercise existing native APIs with an accountant lacking a purchase role."""
    assert admin.cr.dbname.startswith('MANAGEMENT_QA_'), 'Never run fixtures in a live database'
    from odoo import Command
    from odoo.tests.common import new_test_user
    from odoo.addons.step_packing_operations.models.process_control import _INTERNAL
    from odoo.addons.step_packing_operations.models.contract_valuation import _VALUATION
    from odoo.addons.step_packing_fruit_proforma.guards import _FRUIT

    admin = admin(context=dict(admin.context, tracking_disable=True,
        mail_notrack=True, mail_create_nosubscribe=True, mail_notify_force_send=False,
        no_reset_password=True))
    usd, chile = admin.ref('base.USD'), admin.ref('base.cl')
    usd.active = True
    holding = admin['res.company'].create({'name': 'QA171 smoke holding',
        'country_id': chile.id, 'currency_id': usd.id})
    branch = admin['res.company'].create({'name': 'QA171 smoke branch',
        'parent_id': holding.id, 'country_id': chile.id, 'currency_id': usd.id})
    admin.user.company_ids |= holding | branch

    def account(code, kind):
        return admin['account.account'].with_company(holding).create({
            'name': code, 'code': code, 'account_type': kind,
            'reconcile': kind == 'liability_payable',
            'company_ids': [Command.set(holding.ids)]})

    expense = account('QA171EXP', 'expense')
    payable = account('QA171PAY', 'liability_payable')
    producer = admin['res.partner'].create({'name': 'QA171 smoke producer',
        'is_productor': True, 'country_id': chile.id, 'vat': 'CL11111111-1',
        'l10n_cl_sii_taxpayer_type': '1'})
    producer.with_company(branch).property_account_payable_id = payable

    def tax(label, amount):
        group = admin['account.tax.group'].with_company(holding).create({
            'name': label, 'company_id': holding.id})
        return admin['account.tax'].with_company(holding).create({
            'name': label, 'amount': amount, 'amount_type': 'percent',
            'type_tax_use': 'purchase', 'company_id': holding.id,
            'tax_group_id': group.id})

    vat, retention = tax('QA171 VAT', 19), tax('QA171 selected retention', -14)

    def assert_fixture_taxes(stage, business=None):
        taxes = vat | retention
        admin.cr.execute('SELECT id, company_id FROM account_tax WHERE id = ANY(%s) ORDER BY id', [taxes.ids])
        rows = admin.cr.fetchall()
        assert {row[0] for row in rows} == set(taxes.ids), (stage, 'Fixture taxes disappeared', taxes.ids, rows)
        assert all(row[1] == holding.id for row in rows), (stage, 'Wrong fixture tax holding', rows)
        assert taxes.exists() == taxes, (stage, 'ORM fixture existence differs from SQL')
        print('T171_FIXTURE_TAXES_OK ' + json.dumps({'stage': stage, 'rows': rows}), flush=True)
        if business is not None:
            taxes.with_env(business).check_access('read')
            assert taxes.with_env(business).mapped('company_id') == holding.with_env(business)

    assert_fixture_taxes('created')
    category = admin['product.category'].with_company(branch).create({
        'name': 'QA171 smoke category', 'property_cost_method': 'fifo',
        'property_account_expense_categ_id': expense.id})
    kg = admin.ref('uom.product_uom_kgm')
    base = admin['product.product'].with_company(branch).create({
        'name': 'QA171 smoke fruit kilograms', 'purchase_ok': True,
        'step_export_enabled': True, 'categ_id': category.id,
        'uom_id': kg.id, 'uom_po_id': kg.id,
        'property_account_expense_id': expense.id,
        'supplier_taxes_id': [Command.set(vat.ids)]})
    finished = admin['product.product'].with_company(branch).create({
        'name': 'QA171 smoke fruit carton', 'weight': 10, 'is_storable': True,
        'categ_id': category.id, 'step_export_enabled': True,
        'step_export_base_product_id': base.product_tmpl_id.id})
    warehouse = admin['stock.warehouse'].search([('company_id', '=', branch.id)], limit=1)
    if not warehouse:
        warehouse = admin['stock.warehouse'].create({'name': 'QA171 smoke warehouse',
            'code': 'Q171', 'company_id': branch.id})
    journal = admin['account.journal'].with_company(branch).create({
        'name': 'QA171 smoke purchases', 'code': 'Q171P', 'type': 'purchase',
        'company_id': branch.id, 'default_account_id': expense.id,
        'l10n_latam_use_documents': True})
    branch.step_packing_purchase_journal_id = journal
    operator = new_test_user(admin, login='qa171-smoke-accountant',
        context={'no_reset_password': True, 'tracking_disable': True,
                 'mail_create_nosubscribe': True, 'mail_notify_force_send': False},
        groups='account.group_account_manager,stock.group_stock_manager,base.group_multi_company',
        company_id=branch.id, company_ids=[Command.set((holding | branch).ids)])
    assert not operator.has_group('purchase.group_purchase_user')
    business = admin(user=operator, su=False,
        context=dict(admin.context, allowed_company_ids=branch.ids))
    assert not business.su and business.companies == branch
    verify_ui(business)
    assert_fixture_taxes('accountant-ui', business)

    species_by_code = {}
    productions = admin['step.packing.production']
    for code, amount, unit_price in (('33', 600, 2), ('33', 400, 2.01), ('46', 20, 5)):
        if code not in species_by_code:
            species = admin['step.especie'].create({'name': 'QA171 species ' + code,
                'type_especie': 'frutal', 'group_especie': 'fruta_h',
                'company_id': holding.id,
                'company_ids': [Command.set((holding | branch).ids)]})
            policy = {'step_change_subject_vat': code == '46'}
            if code == '46':
                policy['step_withholding_tax_id'] = retention.id
            species.with_company(holding).write(policy)
            group = admin['step.grupo.variedad'].create({'name': 'QA171 group ' + code,
                'especie_id': species.id, 'company_id': holding.id,
                'company_ids': [Command.set((holding | branch).ids)]})
            variety = admin['step.variedad'].create({'name': 'QA171 variety ' + code,
                'cod_variedad': 'QA171' + code, 'especie_id': species.id,
                'grupo_variedad_id': group.id, 'company_id': holding.id,
                'company_ids': [Command.set((holding | branch).ids)]})
            species_by_code[code] = species, variety
        species, variety = species_by_code[code]
        contract = admin['step.producer.purchase.contract'].with_company(holding).create({
            'company_id': holding.id, 'partner_id': producer.id, 'currency_id': usd.id})
        line = admin['step.producer.purchase.contract.product'].create({
            'contract_id': contract.id, 'product_id': base.id, 'species_id': species.id,
            'variety_id': variety.id, 'quantity': amount, 'uom_id': kg.id,
            'price_unit': unit_price})
        admin['step.producer.purchase.contract.installment'].create({
            'contract_id': contract.id, 'product_line_id': line.id,
            'quantity': amount, 'date_due': '2026-11-30'})
        contract.action_confirm()
        tag = admin['stock.quant.package'].with_company(branch).create({
            'name': 'QA171 smoke output %s' % contract.id, 'company_id': branch.id,
            'is_fruit_tag': True, 'step_tag_kind': 'E', 'step_packing_result': 'export',
            'fruit_type': 'conventional', 'step_producer_id': producer.id,
            'especie_id': species.id, 'variedad_id': variety.id,
            'step_tag_line_ids': [Command.create({'producer_id': producer.id,
                'product_id': finished.id, 'quantity': amount / 10,
                'boxes': amount / 10, 'kilos': amount})]})
        production = admin['step.packing.production'].with_company(branch).create({
            'company_id': branch.id, 'date': '2026-11-09',
            'fruit_grower_id': producer.id, 'fruit_species_id': species.id,
            'fruit_variety_id': variety.id, 'contract_id': contract.id,
            'product_id': finished.id, 'product_uom_id': finished.uom_id.id,
            'step_packing_output_tag_ids': [Command.set(tag.ids)]})
        production.with_context(_packing_valuation=_VALUATION).write({
            'valuation_snapshot': production._contract_prices(for_billing=True)})
        production.with_context(_packing_control=_INTERNAL).write({'state': 'closed'})
        productions |= production

    stock_models = ('stock.picking', 'stock.move', 'stock.quant', 'stock.valuation.layer')

    def stock_counts():
        return {model: admin[model].search_count([('company_id', '=', branch.id)])
                for model in stock_models}

    before_stock = stock_counts()
    before_moves = admin['account.move'].search_count([('company_id', '=', branch.id)])
    assert_fixture_taxes('before-monthly', business)
    admin.cr.execute('SELECT id, step_fruit_vat_policy, step_fruit_retention_property_id FROM step_especie WHERE id = ANY(%s) ORDER BY id',
        [[species.id for species, variety in species_by_code.values()]])
    print('T171_FIXTURE_POLICY_ROWS ' + json.dumps(admin.cr.fetchall()), flush=True)
    wizard = business['step.packing.monthly.fruit.bill'].create({
        'company_id': branch.id, 'date_start': '2026-11-01', 'date_end': '2026-11-30',
        'producer_ids': [Command.set(producer.ids)]})
    action = wizard.action_prepare_bills()
    assert action['res_model'] == 'purchase.order'
    orders = business['purchase.order'].search([('step_fruit_proforma', '=', True),
        ('company_id', '=', branch.id), ('partner_id', '=', producer.id)])
    assert len(orders) == 2 and set(orders.mapped('step_fruit_dte_code')) == {'33', '46'}
    assert not orders.invoice_ids and not productions.purchase_bill_id
    assert admin['account.move'].search_count([('company_id', '=', branch.id)]) == before_moves
    assert all(len(order.order_line) == 1 for order in orders)
    ordinary = orders.filtered(lambda order: order.step_fruit_dte_code == '33')
    retained = orders - ordinary
    assert ordinary.order_line.product_qty == 1000
    assert abs(ordinary.order_line.price_unit - 2.004) < 1e-10
    assert ordinary.amount_untaxed == 2004 and ordinary.amount_total == 2384.76
    assert retained.amount_untaxed == 100 and retained.amount_total == 105
    assert retained.order_line.taxes_id == (vat | retention).with_env(business)
    retry = wizard.action_prepare_bills()
    assert retry['domain'] == action['domain']
    assert stock_counts() == before_stock

    report_ref = 'step_packing_fruit_proforma.report_fruit_proforma'
    report = business['ir.actions.report']
    html, _ = report._render_qweb_html(report_ref, orders.ids)
    assert b'PROFORMA' in html and b'QA171' in html
    assert b'Resumen por especie y variedad' in html
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / 't171-smoke-proformas.html').write_bytes(html)
    pdf, filetype = report._render_qweb_pdf(report_ref, orders.ids)
    assert filetype == 'pdf' and pdf.startswith(b'%PDF') and len(pdf) > 5000
    (output / 't171-smoke-proformas.pdf').write_bytes(pdf)

    class LargeAnnexRendered(Exception):
        """Roll back only the synthetic layout rows, preserving the real fixture."""

    original_rows = ordinary.order_line.step_fruit_source_rows
    assert len(original_rows) == 2
    try:
        with admin.cr.savepoint():
            # Layout stress uses the real report and immutable snapshot schema.
            # No extra tags, stock or fiscal documents are created. Keep the
            # summary quantity/net exact and discard these display rows before
            # approval so the subsequent native accounting test uses its sources.
            large_rows = [dict(original_rows[0], tag_name='QA%04d' % number,
                quantity=ordinary.order_line.product_qty / 1000,
                price_unit=ordinary.order_line.price_unit,
                amount=ordinary.amount_untaxed / 1000)
                for number in range(1, 1001)]
            ordinary.order_line.with_context(_fruit_proforma=_FRUIT).write({
                'step_fruit_source_rows': large_rows})
            large_html, _ = report._render_qweb_html(report_ref, ordinary.ids)
            large_tree = etree.HTML(large_html)
            annex_rows = large_tree.xpath("//table[contains(concat(' ', normalize-space(@class), ' '), ' annex ')]/tbody/tr")
            assert len(annex_rows) == 1000
            assert annex_rows[0].xpath('normalize-space(td[1])') == 'QA0001'
            assert annex_rows[-1].xpath('normalize-space(td[1])') == 'QA1000'
            (output / 't171-large-proforma.html').write_bytes(large_html)
            large_pdf, large_type = report._render_qweb_pdf(report_ref, ordinary.ids)
            assert large_type == 'pdf' and large_pdf.startswith(b'%PDF') and len(large_pdf) > 20000
            (output / 't171-large-proforma.pdf').write_bytes(large_pdf)
            raise LargeAnnexRendered()
    except LargeAnnexRendered:
        pass
    assert ordinary.order_line.step_fruit_source_rows == original_rows
    assert not orders.invoice_ids and not productions.purchase_bill_id

    orders.write({'step_fruit_approval_reference': 'QA171 rollback-only approval'})
    orders.action_fruit_approve()
    assert set(orders.mapped('step_fruit_state')) == {'approved'}
    assert not orders.picking_ids and not orders.order_line.move_ids
    ordinary.write({'step_fruit_supplier_invoice_received': True,
        'step_fruit_supplier_document_number': '17133'})
    orders.action_fruit_convert()
    bills = orders.invoice_ids
    assert len(bills) == 2 and set(bills.mapped('state')) == {'draft'}
    assert set(bills.l10n_latam_document_type_id.mapped('code')) == {'33', '46'}
    assert bills.company_id == branch and bills.journal_id == journal
    assert bills.invoice_line_ids.account_id == expense
    assert not retained.invoice_ids.l10n_latam_document_number
    assert retained.invoice_ids.name in (False, '/')
    assert not bills.filtered('posted_before')
    orders.action_fruit_convert()
    assert orders.invoice_ids == bills
    assert wizard.action_prepare_bills()['res_model'] == 'purchase.order'
    assert stock_counts() == before_stock
    assert not orders.picking_ids and not orders.order_line.move_ids
    assert set(orders.order_line.mapped('qty_received')) == {0}
    return {'accountant_without_purchase_role': True, 'outside_accounting_before_approval': True,
            'weighted_price': 2.004, 'summary_lines': 2, 'annex_rows': 3,
            'large_pdf_annex_rows': 1000,
            'draft_documents': ['33', '46'], 'selected_retention': True,
            'no_official_folio': True, 'retry_same_documents': True,
            'stock_preserved': True, 'html_pdf': True}


try:
    for module_name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', module_name)])
        assert module.state == 'installed' and module.latest_version == version
        actual = Path(importlib.import_module('odoo.addons.' + module_name).__file__).resolve().parent
        assert actual == Path(ROOT) / module_name
    scoped = scoped_business_environment(env)
    ui = verify_ui(scoped)
    flow = verify_copy_cycle(env, OUTPUT) if env.cr.dbname.startswith('MANAGEMENT_QA_') else None
    if env.cr.dbname.startswith('MANAGEMENT_QA_CERRO_'):
        assert MONTHLY_FRUIT_PLAN, 'T171 requires the original customer draft in the fresh destination copy'
        from verify_fruit_proforma_case import verify_case
        actual_case = verify_case(env, MONTHLY_FRUIT_PLAN)
        actual_business = scoped_business_environment(env,
            company=env['res.company'].browse(MONTHLY_FRUIT_PLAN['company_id']))
        actual_pdf, actual_type = actual_business['ir.actions.report']._render_qweb_pdf(
            'step_packing_fruit_proforma.report_fruit_proforma', actual_case['proformas'])
        assert actual_type == 'pdf' and actual_pdf.startswith(b'%PDF')
        (Path(OUTPUT) / 't171-actual-proforma.pdf').write_bytes(actual_pdf)
        print('T171_ACTUAL_MONTHLY_CASE_OK ' + json.dumps(actual_case))
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket': 171, 'versions': EXPECTED,
        'existing_profile': scoped.uid, 'ui': ui, 'copy_flow': flow,
        'live_business_writes': False}))
finally:
    env.cr.rollback()
