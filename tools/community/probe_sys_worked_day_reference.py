"""Check that changing a copied day prevents admission of a payroll without work entries."""
import re

from odoo.exceptions import UserError

from probe_sys_october_drafts import amounts, prepare_draft, protect_existing


def probe(env, uid):
    cr=env.cr
    assert re.fullmatch(r'COMMUNITY_SYS_PREVIRED_COHORT_[A-Z0-9_]+',cr.dbname)
    scope=env['hr.payslip'].with_user(uid).with_context(allowed_company_ids=[2],tracking_disable=True)
    assert not scope.env.su and scope.env.company.id==2
    try:
        protect_existing(cr,'hr_payslip',(('hr_payslip','id'),('hr_payslip_line','slip_id'),
                         ('hr_payslip_worked_days','payslip_id'),('hr_payslip_input','payslip_id')))
        cr.execute("""SELECT p.id,p.employee_id,p.contract_id,p.struct_id FROM hr_payslip p WHERE p.id=901
                      AND p.company_id=2 AND p.date_from='2026-10-01' AND p.date_to='2026-10-31'
                      AND p.state IN ('done','paid') AND NOT EXISTS (SELECT 1 FROM hr_work_entry w
                         WHERE w.contract_id=p.contract_id AND w.date_start::date<=p.date_to
                         AND w.date_stop::date>=p.date_from)""")
        source,=cr.fetchall()
        original,draft,stored,*_=prepare_draft(scope,*source,'stored_worked_days')
        assert draft._step_sys_matches_closed_worked_days()
        day,=draft.worked_days_line_ids
        day.number_of_hours-=1
        assert not draft._step_sys_matches_closed_worked_days()
        try:
            draft.compute_sheet()
        except UserError as exc:
            assert 'work entries' in str(exc)
        else:
            raise AssertionError('Altered worked days admitted')
        assert original.state in ('done','paid') and amounts(cr,original.id)==stored and not draft.line_ids
        return {'same_typed_days_admitted':True,'changed_hours_rejected':True,'source_unchanged':True}
    finally:
        cr.rollback()
