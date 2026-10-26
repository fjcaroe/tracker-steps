"""T123 native payment forms, original menus and private invoice/payment flow."""
import importlib
import json
from pathlib import Path
from lxml import etree
from odoo.tools import config
from native_business_profile import scoped_business_environment

try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    scoped = scoped_business_environment(env)
    payment_model = scoped['account.payment']
    arch = etree.fromstring(payment_model.get_view(view_id=scoped.ref('account.view_account_payment_form').id,
                                                  view_type='form')['arch'])
    assert arch.xpath("//button[@name='action_step_select_invoices']")
    assert arch.xpath("//field[@name='step_invoice_allocation_ids']//field[@name='amount']")
    previous = config['test_enable']; config['test_enable'] = True
    try:
        from odoo.tests import Form
    finally:
        config['test_enable'] = previous
    sample = payment_model.search([('company_id', '=', scoped.company.id)], limit=1)
    Form(sample or payment_model, view='account.view_account_payment_form')
    for kind in ('customer', 'vendor'):
        menu = scoped.ref('step_account_treasury.menu_treasury_' + kind + '_payments')
        assert menu.action.res_model == 'account.payment'
        assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
    clone = False
    if env.cr.dbname.startswith('MANAGEMENT_QA_'):
        from odoo.addons.step_treasury_invoice_payment.tests.common import fixture, invoice, payment
        work = scoped['account.payment'].with_context(tracking_disable=True, mail_notrack=True,
            mail_create_nosubscribe=True, mail_notify_force_send=False).env
        data = fixture(work, prefix='QT13')
        for supplier in (False, True):
            kind = 'in_invoice' if supplier else 'out_invoice'
            invoices = invoice(work, data, 100, kind=kind) | invoice(work, data, 200, kind=kind)
            pay = payment(work, data, supplier=supplier)
            wizard = work['step.treasury.payment.invoice.select'].browse(pay.action_step_select_invoices()['res_id'])
            wizard.invoice_ids = invoices; wizard.action_apply()
            pay.step_invoice_allocation_ids.filtered(lambda row: row.invoice_id == invoices[0]).amount = 40
            assert pay.amount == 240
            Form(pay, view='account.view_account_payment_form')
            pay.action_post()
            assert invoices.mapped('amount_residual') == [60, 0]
            assert pay.move_id.state == 'posted'
            assert len(pay.move_id.line_ids.filtered(lambda line: not line.is_operational_exchange_adjustment)) == 3
            assert pay.move_id.line_ids.filtered('step_treasury_invoice_id').step_treasury_invoice_id == invoices
            Form(pay, view='account.view_account_payment_form')
        clone = True
        print('T123_NATIVE_INVOICE_PAYMENT_FLOW_OK company=%s existing_user=%s rollback_required=True' % (scoped.company.id, scoped.uid))
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'tickets': [123], 'versions': EXPECTED,
        'existing_profile': scoped.uid, 'company_id': scoped.company.id, 'native_menu_and_form': True,
        'invoice_selection': True, 'one_counterpart_per_invoice': True, 'clone_flow': clone, 'writes': False}))
finally:
    env.cr.rollback()
