"""Open Steps' expense records and receipts under each original user's company permissions."""
from hashlib import sha256
from pathlib import Path

from lxml import etree
from odoo.exceptions import AccessError
from probe_steps_accounting_history import fingerprint


FIELDS = {
    'hr.expense': ('name', 'date', 'state', 'sheet_id', 'employee_id', 'company_id', 'product_id', 'account_id',
                   'analytic_distribution', 'payment_mode', 'currency_id', 'quantity', 'price_unit', 'tax_ids',
                   'total_amount', 'untaxed_amount', 'total_amount_currency', 'message_main_attachment_id', 'document_count'),
    'hr.expense.sheet': ('name', 'state', 'approval_state', 'payment_state', 'accounting_date', 'employee_id',
                         'user_id', 'company_id', 'journal_id', 'employee_journal_id', 'currency_id', 'total_amount',
                         'untaxed_amount', 'total_tax_amount', 'amount_residual', 'expense_line_ids', 'account_move_ids',
                         'payment_mode', 'payment_method_line_id', 'message_main_attachment_id',
                         'payslip_id', 'refund_in_payslip'),
}
MENUS = ('menu_hr_expense_my_expenses_all', 'menu_hr_expense_all_expenses',
         'menu_hr_expense_sheet_my_reports', 'menu_hr_expense_report', 'menu_hr_expense_account_employee_expenses')
DATABASES = ('MANAGEMENT_QA_STEPS_CRM_20261126U42C', 'COMMUNITY_STEPS_CRM_FISCAL_20261127U45F',
             'COMMUNITY_STEPS_EXPENSE_20261127U50E')


def historical_rows(scope, name):
    model = scope[name]
    fields = sorted(model.fields_get(list(FIELDS[name])).keys() & set(FIELDS[name]))
    proof = {'acl': {mode: model.check_access_rights(mode, raise_exception=False)
                     for mode in ('read', 'create', 'write', 'unlink')}}
    try:
        records = model.search([], order='id')
        values = records.read(fields, load=None)
    except AccessError:
        return {**proof, 'read': False}, model.browse()
    proof.update(read=True, ids=records.ids, fields={
        field: fingerprint([(row['id'], row[field]) for row in values]) for field in fields
    })
    return proof, records


def receipts(scope, records):
    model = scope['ir.attachment']
    try:
        files = model.search([('res_model', '=', records._name), ('res_id', 'in', records.ids)], order='id')
    except AccessError:
        return {'read': False}
    proof = {}
    for attachment in files:
        try:
            raw = attachment.raw
        except AccessError:
            proof[attachment.id] = {'read': False}
            continue
        assert raw and len(raw) == attachment.file_size
        proof[attachment.id] = [attachment.res_id, len(raw), sha256(raw).hexdigest()]
    return proof


def forms(scope, visible_rows):
    try:
        visible = scope['ir.ui.menu']._visible_menu_ids()
    except AccessError:
        return {}
    results = {}
    for key in MENUS:
        menu = scope.ref('hr_expense.' + key)
        if menu.id not in visible:
            results[key] = {'visible': False}
            continue
        action = menu.action
        model = scope[action.res_model]
        view_id = next((view_id for view_id, kind in action.views if kind == 'form'), False)
        view = model.get_view(view_id=view_id, view_type='form')
        arch = etree.fromstring(view['arch'])
        displayed = sorted(set(arch.xpath('//field[not(ancestor::field)]/@name')))
        required = sorted(set(FIELDS[model._name]) & set(displayed) & model.fields_get().keys())
        client = model.get_views([(view['id'], 'form')], {'toolbar': True})['models'][model._name]
        definition = client.get('fields', client)
        result = {'visible': True, 'action': action.id, 'form': view['id'], 'displayed': displayed,
                  'undefined': sorted(set(displayed) - definition.keys()),
                  'buttons': sorted(set(arch.xpath('//button[@type="object"]/@name')))}
        types = [(key, kind) for key, kind in action.views if kind in ('list','kanban','graph','pivot','form','calendar')]
        all_views = model.get_views(types, {'toolbar': True})
        declared = all_views['models'][model._name]
        declared = declared.get('fields', declared)
        result['view_fields_undefined'] = {}
        for kind, descriptor in all_views['views'].items():
            tree = etree.fromstring(descriptor['arch'])
            names = set(tree.xpath('//field[not(ancestor::field)]/@name'))
            result['view_fields_undefined'][kind] = sorted(names - declared.keys())
        # These are record-level reads with this user's permissions. Menu search defaults are company/user dependent.
        rows = visible_rows[model._name]
        if rows:
            loaded = rows.web_read({field: {} for field in required})
            result['opened'] = {field: fingerprint([(row['id'], row[field]) for row in loaded]) for field in required}
            if model._name == 'hr.expense' and 'document_count' in model._fields:
                result['linked_documents'] = {}
                for row in rows:
                    action = row.action_open_attachments()
                    assert action['res_model'] == 'documents.document'
                    assert list(map(tuple, action['domain'])) == [('res_model', '=', row._name), ('res_id', '=', row.id)]
                    documents = scope[action['res_model']].search(action['domain'], order='id')
                    result['linked_documents'][row.id] = [row.document_count, documents.ids]
            if model._name == 'hr.expense.sheet':
                result['posted_entries'] = {}
                for row in rows.filtered('account_move_ids'):
                    entries = row.action_open_account_moves()
                    assert entries['res_model'] == 'account.move' and entries['res_id'] in row.account_move_ids.ids
                    move = scope['account.move'].browse(entries['res_id'])
                    result['posted_entries'][row.id] = fingerprint(move.web_read(
                        {field: {} for field in ('state', 'journal_id', 'currency_id', 'line_ids', 'amount_total')}))
        results[key] = result
    return results


def run(env):
    assert __debug__ and env.cr.dbname in DATABASES
    assert {r.split(':')[0].strip() for r in Path('/proc/net/dev').read_text().splitlines()[2:]} == {'lo'}
    env.cr.rollback()
    env.cr.execute('SET TRANSACTION READ ONLY')
    users = env['res.users'].search([('id', '!=', 1), ('active', '=', True)]) | env.ref('base.public_user')
    cases = []
    for user in users.sorted('id'):
        sets = dict.fromkeys([tuple(user.company_ids.ids), (user.company_id.id,), *((c.id,) for c in user.company_ids)])
        for companies in sets:
            scope = env(user=user.id, su=False, context={'allowed_company_ids': list(companies), 'active_test': False})
            rows = {}
            models = {}
            files = {}
            for name in FIELDS:
                models[name], rows[name] = historical_rows(scope, name)
                files[name] = receipts(scope, rows[name])
            cases.append({'actor': user.id, 'companies': companies, 'models': models, 'files': files,
                          'menus': forms(scope, rows)})
    env.cr.rollback()
    return {'database': env.cr.dbname, 'cases': cases}


def linked_visibility_fixture(env):
    """Measure count and access independently when two existing documents link to a QA expense."""
    assert __debug__ and env.cr.dbname in (DATABASES[0], DATABASES[2])
    assert {r.split(':')[0].strip() for r in Path('/proc/net/dev').read_text().splitlines()[2:]} == {'lo'}
    env.cr.rollback()
    try:
        scopes = {uid: env(user=uid, su=False, context={'allowed_company_ids': [1]}) for uid in (2, 10)}
        existing = {uid: set(scope['documents.document'].search([('type', '=', 'binary')]).ids)
                    for uid, scope in scopes.items()}
        # Use the same two original files in both restorations. Only the relationship changes in this transaction.
        ids = [min(existing[2] & existing[10]), min(existing[2] - existing[10])]
        env.cr.execute('SELECT id,res_model,res_id FROM documents_document WHERE id=ANY(%s) ORDER BY id', [ids])
        before = env.cr.fetchall()
        env.cr.execute("UPDATE documents_document SET res_model='hr.expense',res_id=1 WHERE id=ANY(%s)", [ids])
        env.invalidate_all()
        result = []
        for uid, scope in scopes.items():
            item = scope['hr.expense'].browse(1)
            action = item.action_open_attachments()
            visible = scope[action['res_model']].search(action['domain'], order='id')
            result.append([uid, item.document_count, len(visible), [key in visible.ids for key in ids]])
        assert result == [[2, 2, 2, [True, True]], [10, 2, 1, [True, False]]]
    finally:
        env.cr.rollback()
    env.cr.execute('SELECT id,res_model,res_id FROM documents_document WHERE id=ANY(%s) ORDER BY id', [ids])
    assert env.cr.fetchall() == before
    env.cr.rollback()
    return {'linked_examples': len(ids), 'scopes': result}
