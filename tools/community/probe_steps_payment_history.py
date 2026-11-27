"""Read historical payments and open their original receivable and payable forms as the original Steps users."""
from pathlib import Path

from lxml import etree
from odoo.exceptions import AccessError
from odoo.osv.expression import AND
from odoo.tools.safe_eval import safe_eval
from probe_steps_accounting_history import fingerprint


MODELS = {
    'account.payment': ('name','state','payment_type','partner_type','amount','currency_id','date','journal_id',
                        'company_id','partner_id','destination_account_id','outstanding_account_id','move_id',
                        'payment_method_line_id','partner_bank_id','memo','is_reconciled','is_matched',
                        'reconciled_invoice_ids','reconciled_bill_ids','reconciled_statement_line_ids'),
    'account.partial.reconcile': ('debit_move_id','credit_move_id','amount','debit_amount_currency','credit_amount_currency',
                                  'company_id','max_date','full_reconcile_id','exchange_move_id'),
    'account.full.reconcile': ('partial_reconcile_ids','reconciled_line_ids','exchange_move_id'),
}
MENUS = [('account.menu_action_account_payments_receivable','account.action_account_payments'),
         ('account.menu_action_account_payments_payable','account.action_account_payments_payable')]


def read_records(scope, model, names):
    records=scope[model]
    modes={mode:records.check_access_rights(mode,raise_exception=False) for mode in ('read','write','create','unlink')}
    try:
        ids=records.search([],order='id')
        fields=sorted(records.fields_get(list(names)).keys() & set(names))
        values=ids.read(fields,load=None)
    except AccessError:
        return {'rights':modes,'access':False}
    return {'rights':modes,'access':True,'count':len(ids),'identities':fingerprint(ids.ids),
            'fields':{key:fingerprint([[row['id'],row[key]] for row in values]) for key in fields}}


def open_menus(scope):
    payment=scope['account.payment']
    try:
        visible=scope['ir.ui.menu']._visible_menu_ids()
    except AccessError:
        return None
    menus={}
    for menu_id,action_id in MENUS:
        menu=scope.ref(menu_id)
        report={'visible':menu.id in visible}
        menus[menu_id]=report
        if not report['visible']:
            continue
        action=scope['ir.actions.actions']._for_xml_id(action_id)
        assert menu.action.id==action['id'] and action['res_model']==payment._name
        domain=action.get('domain') or []
        if isinstance(domain,str):
            domain=safe_eval(domain,scope['ir.actions.actions']._get_eval_context())
        context=action.get('context') or {}
        if isinstance(context,str):
            context=safe_eval(context,scope['ir.actions.actions']._get_eval_context())
        records=payment.with_context(**context)
        search_id=action.get('search_view_id') or False
        search=records.get_view(view_id=search_id[0] if isinstance(search_id,(list,tuple)) else search_id,view_type='search')
        filters=etree.fromstring(search['arch'])
        domain_parts=[domain]
        active_filters=[]
        for name,value in context.items():
            if name.startswith('search_default_') and value:
                flt=name.removeprefix('search_default_')
                node,=filters.xpath('//filter[@name=$key]',key=flt)
                domain_parts.append(safe_eval(node.get('domain'),scope['ir.actions.actions']._get_eval_context()))
                active_filters.append(flt)
        assert active_filters==(['inbound_filter'] if menu_id.endswith('receivable') else ['outbound_filter'])
        rows=records.search(AND(domain_parts),order='id')
        report['default_filters']=active_filters
        form_id=next((view for view,kind in action['views'] if kind=='form'),False)
        view=payment.get_view(view_id=form_id,view_type='form')
        tree=etree.fromstring(view['arch'])
        report.update(action=action['id'],form=view['id'],count=len(rows),rows=fingerprint(rows.ids),
            displayed=sorted(set(tree.xpath('//field[not(ancestor::field)]/@name'))),
            object_buttons=sorted(set(tree.xpath('//button[@type="object"]/@name'))))
        if rows:
            known=set(MODELS['account.payment']) & set(payment.fields_get(list(MODELS['account.payment'])))
            opened,=rows[:1].web_read({name:{} for name in sorted(known)})
            assert opened['id']==rows[0].id
            report['opened']={name:fingerprint(value) for name,value in opened.items()}
    return menus


def run(env):
    assert __debug__ and env.cr.dbname in ('MANAGEMENT_QA_STEPS_CRM_20261126U42C',
            'COMMUNITY_STEPS_CRM_INTEGRATED_20261127U46A','COMMUNITY_STEPS_CRM_FISCAL_20261127U45F')
    assert {r.split(':')[0].strip() for r in Path('/proc/net/dev').read_text().splitlines()[2:]}=={'lo'}
    env.cr.rollback()
    env.cr.execute('SET TRANSACTION READ ONLY')
    users=env['res.users'].search([('active','=',True),('id','!=',1)]) | env.ref('base.public_user')
    cases=[]
    for user in users.sorted('id'):
        companies=dict.fromkeys([tuple(user.company_ids.ids),(user.company_id.id,),*((c.id,) for c in user.company_ids)])
        for selection in companies:
            scope=env(user=user.id,su=False,context={'allowed_company_ids':list(selection),'active_test':False,'lang':user.lang})
            cases.append({'actor':user.id,'companies':selection,'models':{m:read_records(scope,m,fields) for m,fields in MODELS.items()},
                          'menus':open_menus(scope)})
    env.cr.rollback()
    return {'database':env.cr.dbname,'cases':cases}
