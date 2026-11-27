"""Replay SyS batch actions on new, guarded drafts for the reference company or the October portfolio."""
import re
from collections import Counter
from uuid import uuid4

from probe_sys_october_drafts import amounts, digest, prepare_draft, protect_existing


def probe(shell, company, uid, calculate=True, followup=False, portfolio=False, payment_reference=False,
          reopen=False):
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
        start, end = ('2026-07-01', '2026-07-31') if payment_reference else ('2026-10-01', '2026-10-31')
        cr.execute("""SELECT id, employee_id, contract_id, struct_id, payslip_run_id FROM hr_payslip
                      WHERE company_id=%s AND state IN ('done','paid') AND date_from=%s
                      AND date_to=%s ORDER BY id""",[company, start, end])
        cases=cr.fetchall()
        assert cases and len({row[4] for row in cases}) == 1 and cases[0][4]
        if payment_reference:
            assert company == 2 and len(cases) == 6
        elif not portfolio:
            assert company == 37 and len(cases) == 5
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
            if followup and action == 'action_payment_report':
                # These reference employees may not have complete banking data.
                # Capture the genuine outcome before exercising the other buttons.
                from odoo.exceptions import UserError
                try:
                    with cr.savepoint():
                        handler = getattr(batch, action, None)
                        if handler is None:
                            progress[action] = {'missing': True, **snapshot()}
                            continue
                        step = handler()
                except UserError as exc:
                    import traceback
                    progress[action] = {'error': type(exc).__name__,
                                        'method': traceback.extract_tb(exc.__traceback__)[-1].name,
                                        'bank_account_message': any(term in str(exc).lower()
                                                                      for term in ('bank', 'banc', 'cuenta')),
                                        **snapshot()}
                    continue
            else:
                step=getattr(batch,action)()
            progress[action]={'result':step.get('type') if isinstance(step,dict) else type(step).__name__,
                              'wizard':step.get('res_model') if isinstance(step,dict) else None,**snapshot()}
            if portfolio and action == 'action_validate':
                from markupsafe import Markup
                from odoo.tools import format_date
                progress[action]['amounts'] = [digest(amounts(cr, draft.id)) for draft in slips]
                progress[action]['headers_match'] = all(
                    draft.move_id and draft.move_id.company_id == draft.company_id
                    and draft.move_id.journal_id == draft.journal_id and draft.move_id.date == draft.date_to
                    and draft.move_id.move_type == 'entry'
                    and draft.move_id.ref == format_date(draft.env, draft.date_to, date_format='MMMM y')
                    and draft.move_id.narration == Markup('<p>%s</p><br>') % draft.number
                    for draft in slips)
            if followup:
                progress[action]['paid_flags'] = len(slips.filtered('paid')) if 'paid' in slips._fields else None
                if action == 'action_payment_report' and isinstance(step,dict):
                    progress[action]['context_keys'] = (sorted(step.get('context',{}))
                                                        if isinstance(step.get('context',{}),dict) else [])
                    progress[action]['wizard_created'] = bool(step.get('res_id'))
                    if payment_reference:
                        import base64
                        import hashlib
                        wizard_model = scope.env[step['res_model']].with_context(**(step.get('context') or {}))
                        wizard = wizard_model.browse(step['res_id']) if step.get('res_id') else wizard_model.create({})
                        assert wizard.payslip_run_id == batch and set(wizard.payslip_ids.ids) == set(slips.ids)
                        assert wizard.export_format == 'csv'
                        response = wizard.generate_payment_report()
                        scope.env.flush_all()
                        contents = base64.b64decode(batch.with_context(bin_size=False).payment_report, validate=True)
                        assert contents and batch.payment_report_filename and batch.payment_report_date
                        progress[action].update(file_bytes=len(contents), sha256=hashlib.sha256(contents).hexdigest(),
                                                response=response.get('type') if isinstance(response,dict) else None)
                if action == 'action_payment_report' and step is None and payment_reference:
                    import base64
                    import csv
                    import hashlib
                    import io
                    contents = base64.b64decode(batch.with_context(bin_size=False).payment_report, validate=True)
                    assert contents and batch.payment_report_filename and batch.payment_report_date
                    header, *rows = csv.reader(io.StringIO(contents.decode('utf-8')))
                    assert len(header) == 6 and rows and all(len(row) == len(header) for row in rows)
                    progress[action].update(file_bytes=len(contents), rows=len(rows),
                                            sha256=hashlib.sha256(contents).hexdigest(),
                                            column_hashes=[digest([r[i] for r in rows]) for i in range(6)])
                    employees = {d.employee_id.name: d for d in slips}
                    assert len(employees) == len(slips)
                    progress[action]['bank_members'] = [bool(d.employee_id.bank_account_id) for d in slips]
                    progress[action]['trusted_members'] = [
                        bool(d.employee_id.bank_account_id and d.employee_id.bank_account_id.allow_out_payment)
                        for d in slips]
                    progress[action]['csv_members'] = [
                        slips.ids.index(employees[row[2]].id) if row[2] in employees else None for row in rows]
                if action == 'action_open_payslips':
                    view_domain = step.get('domain', [])
                    if isinstance(view_domain, str):
                        from odoo.tools.safe_eval import safe_eval
                        view_domain = safe_eval(view_domain, {'active_id': batch.id, 'active_ids': batch.ids})
                    matches = scope.search(view_domain)
                    progress[action].update(member_set_matches=set(matches.ids) == set(slips.ids),
                                            view_mode=step.get('view_mode'), action_id=step.get('id'),
                                            domain_fields=[item[0] for item in view_domain
                                                           if isinstance(item, (tuple,list))],
                                            default_run=(step.get('context') or {}).get('default_payslip_run_id') == batch.id
                                            if isinstance(step.get('context'), dict) else None)
        if reopen:
            assert followup and batch.state == 'draft' and all(s.state == 'draft' for s in slips)
            previous = slips.mapped('move_id')
            assert len(previous) == len(slips)
            progress['attempted'] = 'recompute_after_draft'
            for slip in slips:
                slip.compute_sheet()
            progress['recomputed'] = snapshot()
            for action in ('action_confirm','action_validate'):
                progress['attempted'] = 'retry_' + action
                getattr(batch, action)()
            current = slips.mapped('move_id')
            progress['reclosed'] = {**snapshot(), 'reused_moves': len(current & previous),
                                    'previous_still_present': len(previous.exists())}
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
