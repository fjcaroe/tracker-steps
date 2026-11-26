"""Replay the latest closed full month of each SyS payroll company on new, isolated drafts."""
import re

from probe_sys_october_drafts import amounts, digest, prepare_draft, protect_existing


def probe(env, uid):
    cr = env.cr
    assert re.fullmatch(r'(?:MANAGEMENT_QA_SYS_PREVIRED_|COMMUNITY_SYS_PREVIRED_COHORT_)[A-Z0-9_]+', cr.dbname)
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
        for source_id, employee, contract, structure, company, period, refund in cohort:
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
                    trial.rollback()
            except Exception as exc:
                import traceback
                entry['error'] = type(exc).__name__
                entry['call'] = traceback.extract_tb(exc.__traceback__)[-1].name
                # Keep operator messages private. Do not export private formula text.
                message = str(exc).splitlines()[0][:200]
                if re.fullmatch(r'[A-Za-z0-9 _/.,():-]+',message):
                    entry['reason'] = message
            results.append(entry)
    finally:
        cr.rollback()
    return {'uid':uid, 'native':native, 'samples':results}
