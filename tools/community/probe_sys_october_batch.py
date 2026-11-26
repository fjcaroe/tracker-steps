"""Exercise the original October batch actions on five new drafts under physical history guards."""
import re
from collections import Counter
from uuid import uuid4

from probe_sys_october_drafts import amounts, digest, prepare_draft, protect_existing


def probe(shell, company, uid, calculate=True, followup=False):
    cr = shell.cr
    assert re.fullmatch(r'(?:MANAGEMENT_QA_SYS_PREVIRED_|COMMUNITY_SYS_PREVIRED_COHORT_)[A-Z0-9_]+',cr.dbname)
    scope = shell['hr.payslip'].with_user(uid).with_context(allowed_company_ids=[company],
                tracking_disable=True, mail_notify_force_send=False)
    assert not scope.env.su and scope.env.company.id == company
    progress = {}
    try:
        protect_existing(cr,'hr_payslip',(('hr_payslip','id'),('hr_payslip_line','slip_id'),
              ('hr_payslip_worked_days','payslip_id'),('hr_payslip_input','payslip_id')))
        protect_existing(cr,'hr_payslip_run',(('hr_payslip_run','id'),))
        protect_existing(cr,'account_move',(('account_move','id'),('account_move_line','move_id')))
        cr.execute("""SELECT id, employee_id, contract_id, struct_id, payslip_run_id FROM hr_payslip
                      WHERE company_id=%s AND state IN ('done','paid') AND date_from='2026-10-01'
                      AND date_to='2026-10-31' ORDER BY id""",[company])
        cases=cr.fetchall()
        assert len(cases)==5 and len({row[4] for row in cases})==1
        Run=scope.env['hr.payslip.run']
        original=Run.browse(cases[0][4])
        original.check_access('read')
        new={'name':'STEP_SYS_BATCH_'+uuid4().hex, 'date_start':original.date_start,'date_end':original.date_end,
             'company_id':company}
        if 'journal_id' in Run._fields:
            new['journal_id']=scope.browse(cases[0][0]).journal_id.id
        batch=Run.create(new)
        slips=scope.browse()
        expected=[]
        for source,employee,contract,structure,_ in cases:
            _,draft,stored,*_=prepare_draft(scope,source,employee,contract,structure,'stored_worked_days')
            draft.payslip_run_id=batch
            if calculate:
                draft.compute_sheet()
            slips|=draft
            expected.append(digest(stored))
        def snapshot():
            scope.env.flush_all()
            moves=slips.mapped('move_id')
            return {'batch':batch.state,'slips':dict(Counter(slips.mapped('state'))),
                    'moves':len(moves),'move_states':dict(Counter(moves.mapped('state'))),
                    'move_lines':sum(len(move.line_ids) for move in moves),
                    'matching_drafts':sum(digest(amounts(cr,draft.id))==ref for draft,ref in zip(slips,expected)),
                    'batch_move':bool(batch.move_id) if 'move_id' in batch._fields else None}
        progress['before']=snapshot()
        actions = ['action_confirm','action_validate']
        if followup:
            actions += ['action_open_payslips','action_payment_report','action_paid','action_unpaid','action_draft']
        for action in actions:
            progress['attempted']=action
            step=getattr(batch,action)()
            progress[action]={'result':step.get('type') if isinstance(step,dict) else type(step).__name__,
                              'wizard':step.get('res_model') if isinstance(step,dict) else None,**snapshot()}
            if followup:
                progress[action]['paid_flags'] = len(slips.filtered('paid')) if 'paid' in slips._fields else None
        return progress
    except Exception as exc:
        import traceback
        frame=traceback.extract_tb(exc.__traceback__)[-1]
        progress.update(error=type(exc).__name__,method=frame.name)
        if re.fullmatch(r'[A-Za-z0-9_ .,:/-]{1,170}',str(exc)):
            progress['message']=str(exc)
        return progress
    finally:
        cr.rollback()
