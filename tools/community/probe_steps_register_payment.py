"""Exercise manual payment registration for an existing open invoice inside a rolled-back offline rehearsal."""
from pathlib import Path

from lxml import etree
from probe_steps_accounting_history import fingerprint


def run_one(env, configured=False, supplier=False):
    assert __debug__ and env.cr.dbname in ('MANAGEMENT_QA_STEPS_CRM_20261126U42C',
            'COMMUNITY_STEPS_CRM_FISCAL_20261127U45F','COMMUNITY_STEPS_CRM_INTEGRATED_20261127U46A',
            'COMMUNITY_STEPS_CRM_PAYMENTS_TEST_20261127U46D')
    assert {r.split(':')[0].strip() for r in Path('/proc/net/dev').read_text().splitlines()[2:]}=={'lo'}
    env.cr.rollback()
    user=env['res.users'].browse(10)
    scope=env(user=user.id,su=False,context={'allowed_company_ids':[1],'lang':user.lang,'mail_notify_force_send':False})
    move_type='in_invoice' if supplier else 'out_invoice'
    direction='outbound' if supplier else 'inbound'
    move=scope['account.move'].search([('move_type','=',move_type),('state','=','posted'),('amount_residual','>',0),
                                      ('payment_state','in',['not_paid','partial'])],order='id',limit=1)
    assert move and not scope.su and move.company_id.id==1
    orig=move.amount_residual
    form=move.get_view(view_id=scope.ref('account.view_move_form').id,view_type='form')
    assert etree.fromstring(form['arch']).xpath('//button[@name="action_register_payment"]')
    action=move.action_register_payment()
    assert action['res_model']=='account.payment.register'
    wizard=scope['account.payment.register'].with_context(**action['context']).create({})
    if configured:
        history=scope['account.payment'].search([('company_id','=',move.company_id.id),('payment_type','=',direction),
                ('state','=','paid'),('payment_method_line_id.payment_method_id.code','=','manual'),
                ('payment_method_line_id.payment_account_id','!=',False),('journal_id','in',wizard.available_journal_ids.ids)],order='id',limit=1)
        assert history
        wizard.journal_id=history.journal_id
        wizard.payment_method_line_id=history.payment_method_line_id
    if wizard.payment_method_line_id.payment_method_id.code!='manual':
        manual=wizard.available_payment_method_line_ids.filtered(lambda v:v.payment_method_id.code=='manual')[:1]
        assert manual
        wizard.payment_method_line_id=manual
    assert wizard.payment_method_line_id.payment_method_id.code=='manual' and wizard.amount>0
    target=wizard.action_create_payments()
    assert target['res_model']=='account.payment' and target['view_mode']=='form'
    registered=scope['account.payment'].browse(target['res_id'])
    requested=('state','amount','currency_id','partner_id','company_id','journal_id','payment_method_line_id')
    reopened,=registered.web_read({key:{} for key in requested})
    assert reopened['id']==registered.id and registered.company_id==move.company_id and registered.partner_id==move.partner_id
    matched_documents=registered.reconciled_bill_ids if supplier else registered.reconciled_invoice_ids
    result={'operator':user.id,'original_invoice':move.id,'wizard':action['res_model'],'method':registered.payment_method_line_id.payment_method_id.code,
            'reopened':bool(reopened),'state':registered.state,'company':registered.company_id.id,'journal':registered.journal_id.id,
            'before_and_after':fingerprint([orig,move.amount_residual,wizard.amount,registered.amount,registered.currency_id.id]),
            'invoice_state':move.payment_state,'move_posting':registered.move_id.state,'invoice_link':move in matched_documents,
            'reconciled':registered.is_reconciled,'matched':registered.is_matched}
    result['configured']=bool(registered.payment_method_line_id.payment_account_id)
    if supplier:
        assert registered.payment_type=='outbound' and registered.partner_type=='supplier'
        result['supplier']=True
        result['payable_lines']=fingerprint(sorted((line.account_id.id,line.debit,line.credit,line.amount_currency,
            line.currency_id.id,line.reconciled) for line in registered.move_id.line_ids))
    if registered.state=='in_process':
        view=registered.get_view(view_type='form')
        assert etree.fromstring(view['arch']).xpath('//button[@name="action_validate"]')
        registered.action_validate()
        registered.invalidate_recordset()
        move.invalidate_recordset()
        result['validated']={'payment':registered.state,'invoice':move.payment_state,'residual':fingerprint(move.amount_residual),
                             'ledger':registered.move_id.state,'reconciled':registered.is_reconciled,'matched':registered.is_matched}
    env.cr.rollback()
    return result


def run(env):
    return {'default':run_one(env),'configured':run_one(env,configured=True)}


def run_vendor(env):
    return {'default':run_one(env,supplier=True),'configured':run_one(env,configured=True,supplier=True)}
