"""Observe confirmation with the original Cerro journal and no account mapping."""
from uuid import uuid4

from odoo.exceptions import UserError
from odoo.tools import format_date

from probe_original_draft_amounts import CASES, capture_ytd, run_case
from probe_original_structure_required import require_private_pair


def snapshot(env):
    env.flush_all()
    env.cr.execute("""
        SELECT (SELECT count(*) FROM account_move),
               (SELECT count(*) FROM account_move_line),
               (SELECT count(*) FROM hr_payslip),
               (SELECT count(*) FROM hr_contract),
               (SELECT count(*) FROM hr_work_entry),
               (SELECT count(*) FROM hr_salary_rule
                 WHERE account_debit IS NOT NULL OR account_credit IS NOT NULL)
    """)
    return env.cr.fetchone()


def run(env, database):
    require_private_pair(env, database)
    community = '_HANDOVER_' in database
    before = snapshot(env)
    assert before[2:4] == (0, 0) and before[-1] == 0
    case = next(spec for spec in CASES if spec['structure'] == 2)
    marker = 'STEP_CONFIRM_' + uuid4().hex
    result = {}
    try:
        slip = run_case(env, case, community, {}, marker)
        journal = slip.struct_id.with_company(slip.company_id).journal_id
        journal.check_access('read')
        assert journal and journal.type == 'general' and journal.company_id == slip.company_id
        assert not slip.move_id and slip.state in ('draft', 'verify')
        amounts = capture_ytd(slip, {})
        if community:
            # The test contract can select the existing structure journal.
            # Exercise the original accounting gate before assigning it.
            slip.contract_id.sudo().write({'journal_id': False})
            try:
                slip.with_context(without_compute_sheet=True).action_payslip_done()
            except UserError as exc:
                assert 'OCA salary journal' in str(exc)
            else:
                raise AssertionError('An unconfigured contract bypassed the journal gate')
            assert slip.state in ('draft', 'verify') and not slip.move_id
            assert capture_ytd(slip, {}) == amounts
            assert snapshot(env)[:2] == before[:2]
            slip.contract_id.sudo().write({'journal_id': journal.id})
            assert slip.journal_id == journal
        slip.with_context(without_compute_sheet=True).action_payslip_done()
        assert slip.state == 'done' and slip.move_id and slip.move_id.state == 'draft'
        assert not slip.move_id.line_ids and slip.move_id.move_type == 'entry'
        assert slip.move_id.date == slip.date_to and slip.move_id.journal_id == journal
        period = format_date(slip.env, slip.date_to, date_format='MMMM y', lang_code=slip.env.user.lang)
        assert slip.move_id.ref == period and slip.move_id.name in (False, '/')
        final_amounts = capture_ytd(slip, {})
        totals = snapshot(env)
        assert final_amounts == amounts
        assert totals[:2] == (before[0] + 1, before[1])
        result = {'journal_id': journal.id, 'operator_uid': slip.env.uid,
                  'state': slip.state, 'move_created': bool(slip.move_id),
                  'move_state': slip.move_id.state or None,
                  'move_lines': len(slip.move_id.line_ids),
                  'move_type': slip.move_id.move_type or None,
                  'move_ref_is_period': True,
                  'move_uses_period_end': bool(slip.move_id and slip.move_id.date == slip.date_to),
                  'move_uses_salary_journal': bool(slip.move_id and slip.move_id.journal_id == journal),
                  'accounting_deltas': [totals[i] - before[i] for i in range(2)],
                  'amounts_before': amounts, 'amounts_after': final_amounts,
                  'missing_contract_journal_rejected': community}
    finally:
        env.cr.rollback()
    assert snapshot(env) == before
    return {**result, 'fixture_rolled_back': True}
