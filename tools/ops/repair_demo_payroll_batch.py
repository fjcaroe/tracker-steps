"""Rehearse or apply the approved correction to the October 2026 demo batch."""
import hashlib
import json
from pathlib import Path

from odoo.tools import float_compare


def identity(slips):
    return slips.read(['number', 'employee_id', 'contract_id', 'company_id',
                       'payslip_run_id', 'date_from', 'date_to', 'struct_id'])


def accounting(slips):
    return [{
        'slip': slip.id,
        'id': slip.move_id.id,
        'date': str(slip.move_id.date),
        'journal': slip.move_id.journal_id.id,
        'lines': sorted([
            (line.account_id.id, line.partner_id.id, line.debit, line.credit)
            for line in slip.move_id.line_ids
        ]),
    } for slip in slips]


def payroll(slips):
    return [{
        'slip': slip.id,
        'lines': sorted((line.code, line.total) for line in slip.line_ids),
    } for slip in slips]


def hash_state(state):
    return hashlib.sha256(json.dumps(state, sort_keys=True, default=str).encode()).hexdigest()


try:
    database = env.cr.dbname
    assert database == 'LAB_TAREAS' if APPLY else database.startswith('MANAGEMENT_QA_DEVELOPMENT_')
    company = env['res.company'].browse(CASE['company_id']).exists()
    batch = env['hr.payslip.run'].browse(CASE['batch_id']).exists()
    assert company and batch.company_id == company
    assert str(batch.date_start) == '2026-10-01' and str(batch.date_end) == '2026-10-31'
    assert env['ir.config_parameter'].get_param('step_payroll_simpledigital_base.company_id') == str(company.id)
    if APPLY:
        assert APPROVED_PROOF['package'] == PACKAGE and APPROVED_PROOF['case'] == CASE
    users = env['res.users'].search([
        ('share', '=', False), ('id', '!=', 1), ('company_ids', 'in', company.ids),
    ]).filtered(lambda user: user._is_system()
               and user.has_group('hr_payroll.group_hr_payroll_manager')
               and user.has_group('account.group_account_manager'))
    assert users
    scoped = env(user=users[:1], su=False, context=dict(env.context, allowed_company_ids=company.ids,
        tracking_disable=True, mail_create_nosubscribe=True, mail_notrack=True, payslip_generate_pdf=False))
    env.cr.execute('SELECT id FROM hr_payslip_run WHERE id=%s FOR UPDATE NOWAIT', [batch.id])
    batch = batch.with_env(scoped)
    slips = batch.slip_ids.sorted('id')
    assert batch.state == 'close' and slips.ids == CASE['slip_ids'] and len(slips) == 3
    assert slips.company_id == company and all(s.state == 'done' and not s.paid and not s.paid_date
                                               and not s.queued_for_pdf for s in slips)
    moves = slips.move_id
    assert len(moves) == 3 and moves.company_id == company
    env.cr.execute('SELECT id FROM hr_payslip WHERE id=ANY(%s) ORDER BY id FOR UPDATE NOWAIT', [slips.ids])
    env.cr.execute('SELECT id FROM account_move WHERE id=ANY(%s) ORDER BY id FOR UPDATE NOWAIT', [moves.ids])
    assert all(move.state == 'draft' and not move.posted_before for move in moves)
    assert not moves.line_ids.matched_debit_ids and not moves.line_ids.matched_credit_ids
    assert set(env['hr.payslip'].search([('move_id', 'in', moves.ids)]).ids) == set(slips.ids)
    assert all(s.line_ids.filtered(lambda line: line.code == 'GROSS').total == 0 for s in slips)
    before = {'receipts': identity(slips), 'payroll': payroll(slips), 'draft_entries': accounting(slips)}
    if APPLY:
        assert hash_state(before) == APPROVED_PROOF['before_hash'], 'The demo batch changed since rehearsal'
    mail_domain = [('mail_message_id.model', '=', 'hr.payslip'), ('mail_message_id.res_id', 'in', slips.ids)]
    mails = env['mail.mail'].search_count(mail_domain)
    notifications = env['mail.notification'].search_count(mail_domain)

    slips.action_payslip_cancel()
    batch.action_draft()
    slips.compute_sheet()
    slips.action_payslip_done()

    assert identity(slips) == before['receipts'] and batch.state == 'close'
    assert all(s.state == 'done' and not s.paid and not s.queued_for_pdf for s in slips)
    assert len(slips.move_id) == 3 and all(m.state == 'draft' and not m.posted_before for m in slips.move_id)
    assert slips.move_id.company_id == company
    for slip, previous in zip(slips, before['draft_entries']):
        assert slip.move_id.journal_id.id == previous['journal'] and str(slip.move_id.date) == previous['date']
        totals = {line.code: line.total for line in slip.line_ids}
        assert totals['GROSS'] > 0 and totals['AFP'] and totals['SALUD']
        assert float_compare(sum(slip.move_id.line_ids.mapped('debit')),
                             sum(slip.move_id.line_ids.mapped('credit')),
                             precision_rounding=company.currency_id.rounding) == 0
    assert env['mail.mail'].search_count(mail_domain) == mails
    assert env['mail.notification'].search_count(mail_domain) == notifications
    corrected_payroll = payroll(slips)
    corrected_entries = accounting(slips)
    comparable_entries = [{key: value for key, value in row.items() if key != 'id'} for row in corrected_entries]
    after_hash = hash_state({'payroll': corrected_payroll, 'draft_entries': comparable_entries})
    if APPLY:
        assert after_hash == APPROVED_PROOF['after_hash'], 'The result differs from rehearsal'
    result = {
        'package': PACKAGE, 'case': CASE, 'before_hash': hash_state(before), 'after_hash': after_hash,
        'originals': before, 'corrected_payroll': corrected_payroll, 'corrected_entries': corrected_entries,
    }
    Path(RESULT).write_text(json.dumps(result, indent=2, default=str), encoding='utf-8')
    if APPLY:
        env.cr.commit()
    print('T181_DEMO_BATCH_' + ('CORRECTED' if APPLY else 'REHEARSED') + ' receipts=3 draft_entries=3')
finally:
    env.cr.rollback()
