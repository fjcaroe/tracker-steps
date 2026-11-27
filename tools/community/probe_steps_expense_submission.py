"""Submit, approve and post an employee-paid Steps expense in an isolated transaction."""
from pathlib import Path

from lxml import etree
from probe_steps_accounting_history import fingerprint


def run(env):
    assert __debug__ and env.cr.dbname in ('MANAGEMENT_QA_STEPS_CRM_20261126U42C', 'COMMUNITY_STEPS_EXPENSE_20261127U50E')
    assert {r.split(':')[0].strip() for r in Path('/proc/net/dev').read_text().splitlines()[2:]} == {'lo'}
    env.cr.rollback()
    try:
        scope = env(user=2, su=False, context={'allowed_company_ids': [1], 'mail_notify_force_send': False})
        expense = scope['hr.expense']
        original = expense.search([('state', '=', 'done'), ('payment_mode', '=', 'own_account')], order='id', limit=1)
        assert original and original.create_uid.id == scope.uid == original.sheet_id.user_id.id
        fields = ('employee_id', 'company_id', 'product_id', 'currency_id', 'account_id')
        values = {field: original[field].id for field in fields}
        values.update(name='Verificación privada de rendición', date='2026-11-01', payment_mode='own_account',
                      quantity=original.quantity, total_amount_currency=original.total_amount_currency,
                      tax_ids=[(6, 0, original.tax_ids.ids)], analytic_distribution=original.analytic_distribution)
        original_menu = scope.ref('hr_expense.menu_hr_expense_all_expenses')
        assert original_menu.id in scope['ir.ui.menu']._visible_menu_ids() and original_menu.action.res_model == expense._name
        saved, = expense.web_save(values, {'state': {}, 'employee_id': {}, 'product_id': {}, 'total_amount': {}})
        item = expense.browse(saved['id'])
        assert item.employee_id == original.employee_id and not item.sheet_id and item.total_amount > 0
        target = item.action_submit_expenses()
        assert target['res_model'] == 'hr.expense.sheet'
        sheet = scope['hr.expense.sheet'].browse(target['res_id'])
        assert sheet.expense_line_ids == item and sheet.employee_id == original.employee_id
        view = sheet.get_view(view_type='form')
        arch = etree.fromstring(view['arch'])
        buttons = set(arch.xpath('//button[@type="object"]/@name'))
        assert {'action_submit_sheet', 'action_approve_expense_sheets', 'action_sheet_move_post', 'action_open_account_moves'} <= buttons
        states = [sheet.state]
        sheet.action_submit_sheet()
        states.append(sheet.state)
        result = sheet.action_approve_expense_sheets()
        assert not result, 'unexpected-expense-approval-wizard'
        states.append(sheet.state)
        sheet.action_sheet_move_post()
        states.append(sheet.state)
        action = sheet.action_open_account_moves()
        assert action['res_model'] == 'account.move' and action['res_id'] in sheet.account_move_ids.ids
        move = scope['account.move'].browse(action['res_id'])
        opened, = move.web_read({k: {} for k in ('state', 'journal_id', 'amount_total')})
        assert opened['state'] == 'posted' and move.company_id == sheet.company_id
        ledger = sorted((line.account_id.id, line.partner_id.id, line.currency_id.id, line.debit,
                         line.credit, line.amount_currency, sorted(line.tax_ids.ids)) for line in move.line_ids)
        return {'actor': scope.uid, 'states': states, 'expense_state': item.state, 'journal': move.journal_id.id,
                'posting': move.state, 'taxes': fingerprint(item.tax_ids.ids), 'ledger': fingerprint(ledger),
                'amounts': fingerprint([item.total_amount, sheet.total_amount, sheet.amount_residual, move.amount_total]),
                'posted_lines': len(ledger), 'payment_mode': sheet.payment_mode}
    finally:
        env.cr.rollback()
