"""Compare posted Steps accounting and invoicing through each original user's normal Odoo access."""
from collections import Counter
from hashlib import sha1, sha256
import json
from pathlib import Path

from lxml import etree
from odoo.exceptions import AccessError


TARGETS = {'MANAGEMENT_QA_STEPS_CRM_20261126U42C','COMMUNITY_STEPS_CRM_DOC_20261127U44P',
           'COMMUNITY_STEPS_CRM_SUPPORT_20261127U44H3','COMMUNITY_STEPS_CRM_FISCAL_20261127U45F'}
FIELDS = {
    'account.move': ('name','move_type','state','date','invoice_date','invoice_date_due','journal_id','company_id',
                     'partner_id','commercial_partner_id','currency_id','amount_untaxed','amount_tax','amount_total',
                     'amount_residual','amount_total_signed','payment_state','line_ids','invoice_line_ids',
                     'l10n_latam_document_type_id','l10n_latam_document_number','l10n_cl_dte_status',
                     'l10n_cl_dte_file','l10n_cl_sii_barcode','l10n_cl_reference_ids'),
    'account.move.line': ('move_id','parent_state','journal_id','date','date_maturity','account_id','partner_id',
                          'company_id','currency_id','product_id','quantity','debit','credit','balance','amount_currency',
                          'amount_residual','reconciled','matched_debit_ids','matched_credit_ids','tax_ids','tax_line_id'),
}
MENUS = {
    'out_invoice_type': ('action_move_out_invoice','out_invoice'),
    'in_invoice_type': ('action_move_in_invoice','in_invoice'),
    'out_refund_type': ('action_move_out_refund_type','out_refund'),
    'in_refund_type': ('action_move_in_refund_type','in_refund'),
    'journal_line_form': ('action_move_journal_line','entry'),
}


def fingerprint(value):
    return sha256(json.dumps(value,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()


def values_for_actor(scope, model):
    records = scope[model]
    rights = {op:records.check_access_rights(op,raise_exception=False) for op in ('read','write','create','unlink')}
    try:
        ids = records.search([],order='id')
        fields = sorted(records.fields_get(list(FIELDS[model])).keys() & set(FIELDS[model]))
        rows = ids.read(fields,load=None)
    except AccessError:
        return {'acl':rights,'read':False}
    assert [row['id'] for row in rows]==ids.ids
    out = {'acl':rights,'read':True,'count':len(ids),'identities':fingerprint(ids.ids),
           'fields':{key:fingerprint([[row['id'],row[key]] for row in rows]) for key in fields}}
    if model=='account.move':
        out['states'] = dict(Counter(row['move_type']+'/'+row['state'] for row in rows))
    return out


def forms_for_actor(scope):
    try:
        menus = scope['ir.ui.menu']._visible_menu_ids()
    except AccessError:
        return None
    out = {}
    model = scope['account.move']
    for key,(action_id,kind) in MENUS.items():
        menu = scope.ref('account.menu_action_move_'+key)
        if menu.id not in menus:
            out[kind] = {'visible':False}
            continue
        action = scope['ir.actions.actions']._for_xml_id('account.'+action_id)
        assert menu.action.id==action['id'] and action['res_model']==model._name
        view_id = next((pk for pk,mode in action['views'] if mode=='form'),None)
        view = model.get_view(view_id=view_id or None,view_type='form')
        displayed = sorted(set(etree.fromstring(view['arch'].encode()).xpath('.//field/@name')))
        original = model.search([('move_type','=',kind),('state','=','posted')],order='id',limit=1)
        proof = {'visible':True,'action':action['id'],'form':view['id'],'form_fields':displayed}
        if original:
            assert set(('name','state','journal_id'))<=set(displayed)
            requested = FIELDS['account.move']
            fields = sorted(model.fields_get(list(requested)).keys() & set(requested))
            opened, = original.web_read({name:{} for name in fields})
            assert opened['id']==original.id
            proof.update(opened=original.id,web_values={name:fingerprint(opened[name]) for name in fields})
        out[kind] = proof
    return out


def linked_dte_files(scope):
    model = scope['account.move']
    if 'l10n_cl_dte_file' not in model._fields:
        return {'registered':False}
    try:
        model.check_field_access_rights('read',['l10n_cl_dte_file'])
        moves = model.search([('l10n_cl_dte_file','!=',False)],order='id')
    except AccessError:
        return {'registered':True,'access':False}
    bytes_read = []
    denied = []
    for move in moves:
        attachment = move.l10n_cl_dte_file.with_context(bin_size=False)
        try:
            attachment.check_access('read')
            raw = attachment.raw
        except AccessError:
            denied.append(move.id)
            continue
        assert len(raw)==attachment.file_size and sha1(raw).hexdigest()==attachment.checksum
        bytes_read.append([move.id,attachment.id,len(raw),sha256(raw).hexdigest()])
    return {'registered':True,'access':True,'references':len(moves),'bytes_read':len(bytes_read),'denied':len(denied),
            'amount_and_content':fingerprint(bytes_read),'denied_ids':fingerprint(denied)}


def run(env):
    assert __debug__ and env.cr.dbname in TARGETS
    assert {row.split(':')[0].strip() for row in Path('/proc/net/dev').read_text().splitlines()[2:]}=={'lo'}
    env.cr.rollback()
    env.cr.execute('SET TRANSACTION READ ONLY')
    env.cr.execute('SELECT count(*),count(*) FILTER (WHERE state=\'posted\') FROM account_move')
    count,posted = env.cr.fetchone()
    env.cr.execute('SELECT count(*) FROM account_move_line')
    lines, = env.cr.fetchone()
    assert (count,posted,lines)==(86,84,211)
    users = env['res.users'].search([('id','!=',1),('active','=',True)]) | env.ref('base.public_user')
    cases = []
    for user in users.sorted('id'):
        combinations = dict.fromkeys([tuple(user.company_ids.ids),(user.company_id.id,),*((c.id,) for c in user.company_ids)])
        for companies in combinations:
            scope = env(user=user.id,su=False,context={'allowed_company_ids':list(companies),'active_test':False})
            assert not scope.su
            cases.append({'actor':user.id,'companies':companies,'administrator':user.has_group('base.group_system'),
                          'models':{model:values_for_actor(scope,model) for model in FIELDS},
                          'menus':forms_for_actor(scope),'archived_files':linked_dte_files(scope)})
    env.cr.rollback()
    return {'database':env.cr.dbname,'moves':count,'posted':posted,'lines':lines,'cases':cases}
