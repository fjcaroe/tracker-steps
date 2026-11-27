"""Replay the latest closed full month of each SyS payroll company on new, isolated drafts."""
import re
from decimal import Decimal

from probe_sys_october_drafts import amounts, confirmation, digest, prepare_draft, protect_existing


def summarize_rule_changes(stored, current):
    # Distinguish an absent line, a missing value and the monetary value zero.
    def total(rows):
        return (bool(rows), sum(row[-1] is None for row in rows),
                sum((Decimal(row[-1]) for row in rows if row[-1] is not None), Decimal(0)))

    changed_rows = []
    changed_totals = []
    for code in ("BASIC", "GROSS", "NET"):
        previous = [row for row in stored if row[1] == code]
        computed = [row for row in current if row[1] == code]
        if previous != computed:
            changed_rows.append(code)
        if total(previous) != total(computed):
            changed_totals.append(code)
    return {"changed_rows": changed_rows, "changed_totals": changed_totals}


def probe(env, uid, selected=None, confirm=False, summary=False, components=False, compare_source=None):
    cr = env.cr
    assert (re.fullmatch(r'(?:MANAGEMENT_QA_SYS_PREVIRED_|COMMUNITY_SYS_PREVIRED_COHORT_)[A-Z0-9_]+', cr.dbname)
            or (components and cr.dbname == 'COMMUNITY_SYS_PREVIRED_MODULES_20261127U44VA'))
    native = bool(env['ir.module.module'].sudo().search_count([('state','=','installed'),('license','=','OEEL-1')]))
    cr.execute("""
        WITH full_month AS (
            SELECT * FROM hr_payslip
             WHERE struct_id=4 AND state IN ('done','paid')
               AND date_from=date_trunc('month',date_from)::date
               AND date_to=(date_from+interval '1 month - 1 day')::date
        ), latest AS (SELECT company_id, max(date_to) AS end_date FROM full_month GROUP BY company_id)
        SELECT p.id,p.employee_id,p.contract_id,p.struct_id,p.company_id,p.date_to,p.credit_note
          FROM full_month p JOIN latest l ON (l.company_id,l.end_date)=(p.company_id,p.date_to)
         ORDER BY p.company_id,p.id
    """)
    cohort = cr.fetchall()
    results = []
    try:
        protect_existing(cr, 'hr_payslip', (('hr_payslip','id'),('hr_payslip_line','slip_id'),
                         ('hr_payslip_worked_days','payslip_id'),('hr_payslip_input','payslip_id')))
        if confirm:
            protect_existing(cr, 'account_move', (('account_move', 'id'), ('account_move_line', 'move_id')))
        for source_id, employee, contract, structure, company, period, refund in cohort:
            if selected is not None and source_id not in selected:
                continue
            entry = {'source':source_id,'company':company,'period':period.isoformat()}
            try:
                with cr.savepoint() as trial:
                    scope = env['hr.payslip'].with_user(uid).with_context(
                        allowed_company_ids=[company],tracking_disable=True,mail_notify_force_send=False)
                    assert not scope.env.su and scope.env.company.id == company
                    assert not refund, 'refund-requires-separate-replay'
                    original, draft, stored, *_ = prepare_draft(
                        scope,source_id,employee,contract,structure,'stored_worked_days')
                    draft.compute_sheet()
                    env.flush_all()
                    current = amounts(cr,draft.id)
                    assert current and draft.state in ('draft','verify') and not draft.move_id
                    assert original.state in ('paid','done') and stored == amounts(cr,source_id)
                    entry.update(draft=digest(current), stored=digest(stored), lines=len(current),
                                 equals_stored=current==stored)
                    if summary:
                        entry["summary_rules"] = summarize_rule_changes(stored, current)
                    if components:
                        from sys_rule_variance import analyze
                        entry["changes_by_rule"] = analyze(cr, original, draft, stored, current)
                        if compare_source:
                            entry["dated_value_check"] = compare_source(original, draft, stored, current)
                    if confirm:
                        entry['confirmation'] = confirmation(draft, original, current)
                    trial.rollback()
            except Exception as exc:
                import traceback
                entry['error'] = type(exc).__name__
                frame = traceback.extract_tb(exc.__traceback__)[-1]
                entry['call'] = frame.name
                if '/step_payroll_engine_transition/' in frame.filename and frame.name == 'compute_sheet':
                    entry['policy'] = 'native_contract_review' if 'contratos tienen pendiente' in str(exc) else 'other_transition'
                # Keep operator messages private. Do not export private formula text.
                message = str(exc).splitlines()[0][:200]
                if re.fullmatch(r'[A-Za-z0-9 _/.,():-]+',message):
                    entry['reason'] = message
            results.append(entry)
    finally:
        cr.rollback()
    return {'uid':uid, 'native':native, 'samples':results}
