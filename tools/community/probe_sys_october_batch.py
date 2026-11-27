"""Replay SyS batch actions on new, guarded drafts for the reference company or the October portfolio."""
import re
from collections import Counter
from uuid import uuid4

from probe_sys_october_drafts import amounts, digest, prepare_draft, protect_existing


def probe(shell, company, uid, calculate=True, followup=False, portfolio=False, payment_reference=False,
          reopen=False, individual_payment=False, frozen_reopen=False, standalone=False, member_actions=False):
    cr = shell.cr
    if not __debug__ or not re.fullmatch(r'(?:MANAGEMENT_QA_SYS_PREVIRED_|COMMUNITY_SYS_PREVIRED_COHORT_)[A-Z0-9_]+', cr.dbname):
        raise RuntimeError('Use normal Python and a private SyS payroll restore.')
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
        if standalone:
            import base64
            import csv
            import hashlib
            import io
            source, employee, contract, structure, _ = cases[0]
            _, slip, *_ = prepare_draft(scope, source, employee, contract, structure, 'stored_worked_days')
            assert not slip.payslip_run_id
            slip.number = 'STEP_SYS_WITHOUT_BATCH_' + uuid4().hex
            slip.compute_sheet()
            slip.with_context(without_compute_sheet=True).action_payslip_done()
            assert slip.state == 'done' and not slip.payslip_run_id
            progress['attempted'] = 'single_without_batch'
            result = slip.action_payslip_payment_report()
            scope.env.flush_all()
            slip.invalidate_recordset()
            raw = base64.b64decode(b''.join(slip.with_context(bin_size=False).payment_report.split()), validate=True)
            header, row = csv.reader(io.StringIO(raw.decode()))
            assert len(header) == len(row) == 6 and row[2] == slip.employee_id.name
            return {'returned': result.get('type') if isinstance(result, dict) else type(result).__name__,
                    'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
                    'filename_is_slip': slip.payment_report_filename == slip.name + '.csv',
                    'filename_is_number': slip.payment_report_filename == slip.number + '.csv',
                    'has_date': bool(slip.payment_report_date)}
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
            if action == 'action_validate' and member_actions:
                from odoo.exceptions import UserError
                with cr.savepoint() as trial:
                    first = slips[:1]
                    button = getattr(first, 'action_register_payment', None)
                    if button:
                        try:
                            with cr.savepoint():
                                window = button()
                        except UserError as exc:
                            progress['register'] = {'error': type(exc).__name__}
                        else:
                            progress['register'] = {
                                'result': window.get('type') if isinstance(window, dict) else type(window).__name__,
                                'wizard': window.get('res_model') if isinstance(window, dict) else None}
                    else:
                        progress['register'] = {'missing': True}
                    for label, func, selected in [('pay_first', 'action_payslip_paid', first),
                                                  ('pay_rest', 'action_payslip_paid', slips - first),
                                                  ('unpay_first', 'action_payslip_unpaid', first),
                                                  ('unpay_rest', 'action_payslip_unpaid', slips - first)]:
                        progress['attempted'] = label
                        result = getattr(selected, func)()
                        progress[label] = {'result': type(result).__name__, **snapshot()}
                        if label == 'pay_first' and batch.state == 'close':
                            import base64
                            import csv
                            import io
                            with cr.savepoint() as mixed:
                                try:
                                    batch.action_payment_report()
                                    scope.env.flush_all()
                                    batch.invalidate_recordset()
                                    blob = batch.with_context(bin_size=False).payment_report
                                    data = base64.b64decode(b''.join(blob.split()), validate=True)
                                    _, *rows = csv.reader(io.StringIO(data.decode()))
                                    progress['mixed_report'] = {'rows': len(rows),
                                        'includes_paid': first.employee_id.name in [r[2] for r in rows]}
                                except UserError as exc:
                                    progress['mixed_report'] = {'error': type(exc).__name__}
                                mixed.rollback()
                            with cr.savepoint() as mixed:
                                batch.action_paid()
                                progress['pay_mixed_batch'] = snapshot()
                                first.action_payslip_unpaid()
                                batch.action_unpaid()
                                progress['unpay_mixed_batch'] = snapshot()
                                mixed.rollback()
                    trial.rollback()
            if action == 'action_validate' and individual_payment:
                import base64
                import hashlib
                chosen = slips[:1]
                with cr.savepoint() as individual:
                    result = chosen.action_payslip_payment_report()
                    scope.env.flush_all()
                    scope.env.invalidate_all(flush=False)
                    stored = chosen.with_context(bin_size=False).payment_report
                    report = base64.b64decode(b''.join(stored.split()), validate=True) if stored else b''
                    progress['single_report'] = {
                        'returned':result.get('type') if isinstance(result,dict) else type(result).__name__,
                        'file_bytes':len(report), 'sha256':hashlib.sha256(report).hexdigest() if report else None,
                        'also_batch':bool(batch.with_context(bin_size=False).payment_report),
                        'also_other_slips':len((slips - chosen).filtered('payment_report')),
                        'filename_is_batch': chosen.payment_report_filename == batch.name + '.csv',
                        'filename_is_slip': chosen.payment_report_filename == chosen.name + '.csv'}
                    individual.rollback()
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
                        batch.invalidate_recordset(['payment_report'])
                        contents = base64.b64decode(b''.join(batch.with_context(bin_size=False).payment_report.split()),
                                                    validate=True)
                        assert contents and batch.payment_report_filename and batch.payment_report_date
                        progress[action].update(file_bytes=len(contents), sha256=hashlib.sha256(contents).hexdigest(),
                                                response=response.get('type') if isinstance(response,dict) else None)
                if action == 'action_payment_report' and step is None and payment_reference:
                    import base64
                    import csv
                    import hashlib
                    import io
                    scope.env.flush_all()
                    batch.invalidate_recordset(['payment_report'])
                    contents = base64.b64decode(b''.join(batch.with_context(bin_size=False).payment_report.split()),
                                                validate=True)
                    assert contents and batch.payment_report_filename and batch.payment_report_date
                    header, *rows = csv.reader(io.StringIO(contents.decode('utf-8')))
                    assert len(header) == 6 and rows and all(len(row) == len(header) for row in rows)
                    progress[action].update(file_bytes=len(contents), rows=len(rows),
                                            filename_matches_batch=batch.payment_report_filename == batch.name + '.csv',
                                            file_date_matches_record=all(r[0] == batch.payment_report_date.strftime('%d/%m/%Y')
                                                                         for r in rows),
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
                    if 'payment_report' in slips._fields:
                        slips.invalidate_recordset(['payment_report'])
                        member_files = [
                            base64.b64decode(b''.join(d.with_context(bin_size=False).payment_report.split()), validate=True)
                            if d.with_context(bin_size=False).payment_report else b'' for d in slips]
                        progress[action]['slip_files'] = [bool(blob) for blob in member_files]
                        progress[action]['member_reports_match_batch'] = [blob == contents for blob in member_files]
                        by_employee = {r[2]: r for r in rows}
                        progress[action]['member_reports_only_own_row'] = [
                            list(csv.reader(io.StringIO(blob.decode()))) == [header, by_employee[d.employee_id.name]]
                            for d, blob in zip(slips, member_files)]
                        progress[action]['member_filenames_match'] = [
                            d.payment_report_filename == batch.payment_report_filename for d in slips]
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
        if reopen or frozen_reopen:
            assert followup and batch.state == 'draft' and all(s.state == 'draft' for s in slips)
            previous = slips.mapped('move_id')
            assert len(previous) == len(slips)
            progress['attempted'] = 'recompute_after_draft'
            if frozen_reopen:
                from odoo.exceptions import UserError
                guards = []
                for slip in slips:
                    before = digest(amounts(cr, slip.id))
                    try:
                        with cr.savepoint():
                            slip.compute_sheet()
                    except UserError:
                        guards.append(slip.step_history_locked and digest(amounts(cr, slip.id)) == before)
                    else:
                        guards.append(False)
                assert all(guards)
                progress['protected_frozen_slips'] = len(guards)
            else:
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
