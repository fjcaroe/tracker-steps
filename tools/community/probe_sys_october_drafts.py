"""Replay the five SyS October payrolls on *new* slips in a disposable restore.

Run in an offline Odoo shell under the environment lock. Stored amounts are
read from SQL. Only the new draft enters the current engine. Compare reference
and candidate receipts separately from any comparison with historical amounts.
"""
import hashlib
import json
import re
from decimal import Decimal
from uuid import uuid4

from odoo import Command


def amounts(cr, slip_id):
    cr.execute("""
        SELECT salary_rule_id, code, amount::text, quantity::text, rate::text, total::text
          FROM hr_payslip_line WHERE slip_id = %s ORDER BY salary_rule_id, id
    """, [slip_id])
    return [(rule, code, *(format(Decimal(value).normalize(), 'f') if value is not None else None
                           for value in values)) for rule, code, *values in cr.fetchall()]


def digest(rows):
    return hashlib.sha256(json.dumps(rows, separators=(',', ':')).encode()).hexdigest()


def protect_existing(cr, source, relations):
    # All identifiers below come from the two fixed call sites. OLD and NEW
    # must both be checked because a child can be reassigned to a different parent.
    protected = 'sys_original_' + source
    cr.execute(f"CREATE TEMP TABLE {protected} ON COMMIT DROP AS SELECT id FROM {source}")
    cr.execute(f"ALTER TABLE pg_temp.{protected} ADD PRIMARY KEY(id)")
    cr.execute(f"""
        CREATE FUNCTION pg_temp.reject_{source}_write() RETURNS trigger LANGUAGE plpgsql AS $guard$
        BEGIN
            IF TG_OP <> 'INSERT' AND EXISTS (SELECT FROM pg_temp.{protected}
                    WHERE id = (to_jsonb(OLD)->>TG_ARGV[0])::int) THEN
                RAISE EXCEPTION 'Original record changed during payroll replay';
            END IF;
            IF TG_OP <> 'DELETE' AND EXISTS (SELECT FROM pg_temp.{protected}
                    WHERE id = (to_jsonb(NEW)->>TG_ARGV[0])::int) THEN
                RAISE EXCEPTION 'Original record changed during payroll replay';
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END $guard$
    """)
    for table, key in relations:
        cr.execute(f"CREATE TRIGGER sys_protect_before_replay BEFORE INSERT OR UPDATE OR DELETE "
                   f"ON public.{table} FOR EACH ROW EXECUTE FUNCTION pg_temp.reject_{source}_write('{key}')")


def day_facts(slip):
    slip.env.cr.execute("""
        SELECT work_entry_type_id, number_of_days::text, number_of_hours::text
          FROM hr_payslip_worked_days WHERE payslip_id = %s
         ORDER BY work_entry_type_id, number_of_days, number_of_hours
    """, [slip.id])
    return slip.env.cr.fetchall()


def admit_original_children(slip):
    for model, parent in (('hr.payslip.line', 'slip_id'), ('hr.payslip.input', 'payslip_id'),
                          ('hr.payslip.worked_days', 'payslip_id')):
        records = slip.env[model]
        slip.env.cr.execute(f"SELECT id FROM {records._table} WHERE {parent} = %s", [slip.id])
        records.browse([r[0] for r in slip.env.cr.fetchall()]).check_access('read')


def confirmation(draft, original, calculated):
    from markupsafe import Markup
    from odoo.exceptions import AccessError
    from odoo.tools import format_date
    cr = draft.env.cr
    draft.with_context(without_compute_sheet=True).action_payslip_done()
    draft.env.flush_all()
    assert draft.state == 'done' and draft.move_id and draft.move_id != original.move_id
    assert calculated == amounts(cr, draft.id)
    move = draft.move_id
    move.check_access('read')
    source = original.move_id
    comparable = bool(source)
    if source:
        try:
            source.check_access('read')
        except AccessError:
            # Preserve the original company boundary even if the old foreign
            # key references a journal entry outside the operator's company.
            comparable = False
    cr.execute("SELECT id FROM pg_temp.sys_original_account_move WHERE id = %s", [move.id])
    assert not cr.fetchall()
    fields = ('state', 'move_type', 'date', 'journal_id', 'company_id')
    period = format_date(draft.env, draft.date_to, date_format='MMMM y')
    return {'move_state': move.state, 'move_lines': len(move.line_ids),
            'reference_matches_formatted_period': move.ref == period,
            'narration_matches_slip_number': move.narration == Markup('<p>%s</p><br>') % draft.number,
            'date_matches_period_end': move.date == draft.date_to,
            'single_unassigned_partner': not move.partner_id,
            'matches_original_header': all(move[k] == source[k] for k in fields) if comparable else None,
            'matches_original_line_count': len(move.line_ids) == len(source.line_ids) if comparable else None,
            'closed_payroll_amounts_unchanged': True}


def prepare_draft(scope, original_id, employee, contract, structure, day_source):
    cr = scope.env.cr
    original = scope.browse(original_id)
    original.check_access('read')
    admit_original_children(original)
    assert original.state in ('done', 'paid')
    assert (original.employee_id.id, original.contract_id.id, original.struct_id.id) == (employee, contract, structure)
    stored = amounts(cr, original_id)
    assert stored
    marker = 'STEP_SYS_REPLAY_' + uuid4().hex
    draft = scope.create({'name': marker, 'number': marker,
                          'employee_id': employee, 'contract_id': contract, 'struct_id': structure,
                          'company_id': scope.env.company.id, 'date_from': original.date_from, 'date_to': original.date_to})
    assert draft.id != original_id and draft.number == marker and draft.state == 'draft'
    assert not draft.input_line_ids and not original.input_line_ids
    if day_source == 'current_work_entries':
        days = draft._get_worked_day_lines()
    else:
        days = [dict(name=day.name, sequence=day.sequence, work_entry_type_id=day.work_entry_type_id.id,
                     number_of_days=day.number_of_days, number_of_hours=day.number_of_hours, code=day.code)
                for day in original.worked_days_line_ids]
    historical_days = day_facts(original)
    accepted = draft.worked_days_line_ids._fields
    writable = ('name', 'sequence', 'work_entry_type_id', 'number_of_days', 'number_of_hours')
    rows = [{k: row[k] for k in writable if k in row and k in accepted} for row in days]
    if 'contract_id' in accepted and not accepted['contract_id'].related:
        for raw, values in zip(days, rows):
            values.update(code=raw['code'], contract_id=contract)
    draft.worked_days_line_ids = [Command.clear(), *[Command.create(row) for row in rows]]
    draft.worked_days_line_ids.flush_recordset()
    entered_days = day_facts(draft)
    if day_source == 'stored_worked_days':
        assert entered_days == historical_days
    return original, draft, stored, historical_days, entered_days


def replay(scope, original_id, employee, contract, structure, day_source, confirm):
    original, draft, stored, historical_days, entered_days = prepare_draft(
        scope, original_id, employee, contract, structure, day_source)
    marker = draft.number
    cr = scope.env.cr
    draft.compute_sheet()
    assert draft.state in ('draft','verify') and not draft.move_id and draft.number == marker
    draft.line_ids.flush_recordset(['salary_rule_id','code','amount','quantity','rate','total'])
    draft.worked_days_line_ids.flush_recordset()
    current = amounts(cr, draft.id)
    assert current and stored == amounts(cr, original_id)
    result = {'source_slip': original_id, 'historical_sha256': digest(stored), 'draft_sha256': digest(current),
            'historical_lines': len(stored), 'draft_lines': len(current),
            'historical_net_rules': [r[0] for r in stored if r[1]=='NET'],
            'draft_net_rules': [r[0] for r in current if r[1]=='NET'],
            'historic_amounts_match_current_draft': current == stored, 'day_source': day_source,
            'historical_day_rows': len(historical_days), 'entered_day_rows': len(entered_days),
            'entered_days_match_historical': entered_days == historical_days,
            'calculated_days_match_historical': day_facts(draft) == historical_days}
    if confirm:
        result['confirmation'] = confirmation(draft, original, current)
    return result


def probe(env, company, uid, confirm=False):
    assert (env.cr.dbname == 'COMMUNITY_SYS_FINAL_RESTORED_20261127U46R' or
            re.fullmatch(r'(?:MANAGEMENT_QA_SYS_PREVIRED_|COMMUNITY_SYS_PREVIRED_)[A-Z0-9_]+', env.cr.dbname))
    scope = env['hr.payslip'].with_user(uid).with_context(
        allowed_company_ids=[company], tracking_disable=True, mail_notify_force_send=False)
    assert not scope.env.su and scope.env.company.id == company
    cr = env.cr
    try:
        protect_existing(cr, 'hr_payslip', (
            ('hr_payslip', 'id'), ('hr_payslip_line', 'slip_id'),
            ('hr_payslip_input', 'payslip_id'), ('hr_payslip_worked_days', 'payslip_id')))
        if confirm:
            protect_existing(cr, 'account_move', (('account_move', 'id'), ('account_move_line', 'move_id')))
        cr.execute("""SELECT id, employee_id, contract_id, struct_id FROM hr_payslip
            WHERE company_id=%s AND date_from='2026-10-01' AND date_to='2026-10-31'
            AND state IN ('done','paid') ORDER BY id""", [company])
        originals = cr.fetchall()
        assert len(originals) == 5
        result = []
        for day_source in (('stored_worked_days',) if confirm else ('current_work_entries', 'stored_worked_days')):
            for row in originals:
                # Independent rollbacks keep a prior draft out of YTD/period searches.
                with cr.savepoint() as trial:
                    result.append(replay(scope, *row, day_source=day_source, confirm=confirm))
                    trial.rollback()
        return {'uid': uid, 'company': company, 'rows': result}
    finally:
        cr.rollback()
