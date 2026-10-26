"""Fixtures used only by rollback tests and private destination-copy probes."""
from odoo import Command, fields


def fixture(env, prefix='Q123'):
    company = env.company
    def account(suffix, kind, reconcile=False):
        return env['account.account'].create({'name': prefix + ' ' + kind, 'code': prefix + suffix,
            'company_ids': [Command.set(company.ids)], 'account_type': kind, 'reconcile': reconcile})
    data = {'company': company, 'date': fields.Date.to_date('2026-10-26')}
    for name, suffix, kind, reconcile in [('receivable','1','asset_receivable',True), ('payable','2','liability_payable',True),
        ('income','3','income',False), ('expense','4','expense',False), ('bank_account','5','asset_cash',True),
        ('receipt','6','asset_current',True), ('outgoing','7','asset_current',True)]:
        data[name] = account(suffix, kind, reconcile)
    for kind, code in [('sale','S'), ('purchase','P'), ('bank','B')]:
        values = {'name': prefix + ' ' + kind, 'code': prefix + code, 'type': kind, 'company_id': company.id}
        if kind == 'bank': values['default_account_id'] = data['bank_account'].id
        if 'l10n_latam_use_documents' in env['account.journal']._fields:
            values['l10n_latam_use_documents'] = False
        data[kind] = env['account.journal'].create(values)
    for direction, key in [('inbound','receipt'), ('outbound','outgoing')]:
        method = data['bank'][direction + '_payment_method_line_ids'].filtered(lambda row: row.code == 'manual')[:1]
        assert method
        method.payment_account_id = data[key]
        data[direction] = method
    partner = env['res.partner'].create({'name': prefix + ' cliente proveedor'})
    partner.with_company(company).write({'property_account_receivable_id': data['receivable'].id,
                                        'property_account_payable_id': data['payable'].id})
    data['partner'] = partner
    return data


def invoice(env, data, amount=100, kind='out_invoice', currency=None, post=True, partner=None, term=None):
    supplier = kind == 'in_invoice'
    record = env['account.move'].create({'move_type': kind, 'company_id': data['company'].id,
        'journal_id': data['purchase' if supplier else 'sale'].id,
        'partner_id': (partner or data['partner']).id, 'invoice_date': data['date'], 'date': data['date'],
        'invoice_payment_term_id': term.id if term else False,
        'currency_id': (currency or data['company'].currency_id).id,
        'invoice_line_ids': [Command.create({'name': 'QA123 documento', 'quantity': 1, 'price_unit': amount,
            'tax_ids': [Command.clear()], 'account_id': data['expense' if supplier else 'income'].id})]})
    if post: record.action_post()
    return record


def payment(env, data, invoices=(), amounts=None, supplier=False, currency=None):
    amounts = amounts if amounts is not None else [inv.amount_residual for inv in invoices]
    direction = 'outbound' if supplier else 'inbound'
    return env['account.payment'].create({'company_id': data['company'].id, 'partner_id': data['partner'].id,
        'payment_type': direction, 'partner_type': 'supplier' if supplier else 'customer',
        'journal_id': data['bank'].id, 'payment_method_line_id': data[direction].id,
        'currency_id': (currency or data['company'].currency_id).id, 'date': data['date'],
        'amount': sum(amounts), 'step_invoice_allocation_ids': [Command.create({'invoice_id': inv.id, 'amount': amount})
            for inv, amount in zip(invoices, amounts)]})
