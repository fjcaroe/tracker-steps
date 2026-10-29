"""Read-only admission and cache restoration of real, stored payroll history."""
from odoo import _
from odoo.exceptions import AccessError, UserError
from decimal import Decimal

SNAPSHOTS={'hr_payslip':('basic_wage','gross_wage','net_wage'),
           'hr_payslip_worked_days':('amount','is_paid')}


def history_protected(slip):
    return (slip.state not in ('draft','verify')
            or ('paid' in slip._fields and slip.paid)
            or ('step_history_locked' in slip._fields and slip.step_history_locked))


def columns(cr,table):
    cr.execute("SELECT attname FROM pg_attribute WHERE attrelid=to_regclass(%s) AND attnum>0 AND NOT attisdropped",(table,))
    return {row[0] for row in cr.fetchall()}


def protected_sql(names):
    parts=["s.state NOT IN ('draft','verify')"]
    if 'paid' in names:parts.append('coalesce(s.paid,false)')
    if 'step_history_locked' in names:parts.append('coalesce(s.step_history_locked,false)')
    return '('+' OR '.join(parts)+')'


def assert_history_snapshots(cr):
    """Run BEFORE ORM auto-init. Missing history must never become invented zeroes."""
    names=columns(cr,'hr_payslip')
    if not names:return
    predicate=protected_sql(names)
    for table,fields in SNAPSHOTS.items():
        source='hr_payslip s' if table=='hr_payslip' else 'hr_payslip_worked_days h JOIN hr_payslip s ON s.id=h.payslip_id'
        alias='s' if table=='hr_payslip' else 'h'
        cr.execute('SELECT 1 FROM '+source+' WHERE '+predicate+' LIMIT 1')
        if not cr.fetchone():continue
        present=columns(cr,table)
        if set(fields)-present:
            raise UserError(_('Adopt original stored payroll snapshots before upgrading: %s',table))
        empty=' OR '.join(alias+'.'+name+' IS NULL' for name in fields)
        cr.execute('SELECT 1 FROM '+source+' WHERE '+predicate+' AND ('+empty+') LIMIT 1')
        if cr.fetchone():
            raise UserError(_('Original closed payroll snapshots are incomplete: %s',table))


def restore_snapshot_cache(records):
    """Restore original SQL values without arithmetic, dirty writes or audit changes."""
    if not records:return
    names=SNAPSHOTS[records._table]
    records.check_access('read')
    records.env.cr.execute('SELECT id,'+','.join(names)+' FROM '+records._table+' WHERE id=ANY(%s)',(records.ids,))
    rows={row[0]:row[1:] for row in records.env.cr.fetchall()}
    for record in records:
        original=rows.get(record.id)
        if original is None or any(value is None for value in original):
            raise UserError(_('Adopt original closed payroll amounts before reading this history.'))
        for name,value in zip(names,original):
            field=record._fields[name]
            record.env.cache.set(record,field,field.convert_to_cache(value,record,validate=False))


def assert_mutable(parents):
    parents.check_access('read')
    if any(history_protected(slip) for slip in parents):
        raise UserError(_('Closed payroll history cannot be changed or removed. Create a correction instead.'))


def assert_community_engine(cr):
    cr.execute("SELECT 1 FROM ir_module_module WHERE name='hr_payroll' AND state NOT IN ('uninstalled','uninstallable') LIMIT 1")
    if cr.fetchone():
        raise UserError(_('Retire the native engine through the audited identity conversion before installing the Community bridge.'))


def stored_line_total(lines):
    """Read the authoritative SQL snapshot, including zero, without recomputation."""
    if not lines:return 0.0
    if lines._name!='hr.payslip.line':raise ValueError('Expected actual payroll lines')
    lines.check_access('read')
    if any(not isinstance(ident,int) for ident in lines.ids):
        raise UserError(_('Save the real payroll lines before exporting stored totals.'))
    lines.env.cr.execute('SELECT id,total FROM hr_payslip_line WHERE id=ANY(%s)',(lines.ids,))
    rows=lines.env.cr.fetchall()
    if len(rows)!=len(lines) or any(value is None for ident,value in rows):
        raise UserError(_('Original stored payroll line totals are incomplete; no amount will be reconstructed.'))
    return sum(value for ident,value in rows)


def _stored_payslip_rows(payslips):
    """Aggregate authoritative line snapshots only after checking complete visibility.

    A record-rule-filtered one2many must not turn a hidden contribution into zero.
    SQL is used for stored values, never to authorize access or recalculate totals.
    """
    if payslips._name != 'hr.payslip':
        raise ValueError('Expected actual payroll slips')
    payslips.check_access('read')
    if not payslips:
        return []
    if any(not isinstance(ident, int) for ident in payslips.ids) or payslips.exists() != payslips:
        raise UserError(_('Save the real payroll slips before exporting stored totals.'))
    lines = payslips.env['hr.payslip.line']
    lines.check_access('read')
    lines.check_field_access_rights('read', ['slip_id', 'code', 'total', 'salary_rule_id'])
    # Archived OCA lines remain historical data; active_test is not a salary ACL.
    visible = lines.with_context(active_test=False).search([('slip_id', 'in', payslips.ids)])
    payslips.env.cr.execute(
        'SELECT id,slip_id,code,total,salary_rule_id FROM hr_payslip_line WHERE slip_id=ANY(%s)',
        (payslips.ids,))
    rows = payslips.env.cr.fetchall()
    if set(visible.ids) != {row[0] for row in rows}:
        raise AccessError(_('The payroll export requires access to every original salary line.'))
    if any(total is None or not code for ident, slip_id, code, total, rule_id in rows):
        raise UserError(_('Original stored payroll line totals or codes are incomplete; no amount will be reconstructed.'))
    return rows


def stored_payslip_line_components(payslips, rule_codes=None):
    """Authorized raw line snapshots, never summed or reconstructed from factors.

    Distinct rule identities remain distinct for diagnosis. Use the guarded
    aggregate API for code totals; this reader never chooses an essential rule.
    """
    original=_stored_payslip_rows(payslips)
    if not original:return []
    payslips.env['hr.payslip.line'].check_field_access_rights('read',['amount','quantity','rate'])
    payslips.env.cr.execute('SELECT id,slip_id,code,salary_rule_id,amount,quantity,rate,total FROM hr_payslip_line WHERE slip_id=ANY(%s) ORDER BY slip_id,id',(payslips.ids,))
    rows=payslips.env.cr.fetchall()
    expected={ident:(slip,code,total,rule) for ident,slip,code,total,rule in original}
    if {row[0]:(row[1],row[2],row[7],row[3]) for row in rows}!=expected:
        raise UserError(_('Original payroll line identity changed during snapshot reading.'))
    if any(value is None or not Decimal(str(value)).is_finite() for row in rows for value in row[4:]):
        raise UserError(_('Original stored payroll line components are incomplete or non-finite; no amount will be reconstructed.'))
    requested={rule_codes} if isinstance(rule_codes,str) else set(rule_codes or ())
    names=('id','slip_id','code','salary_rule_id','amount','quantity','rate','total')
    return [dict(zip(names,row)) for row in rows if not requested or row[2] in requested]


def stored_payslip_code_totals(payslips, rule_codes=None):
    """Aggregate stored codes; essential concepts require one original rule identity.

    Repeated rows of the same rule remain additive. Two different rules called
    NET are not an authorized choice of financial meaning, even if one is zero.
    Filtering a nonessential code does not select or repair an ambiguous NET.
    """
    rows = _stored_payslip_rows(payslips)
    requested = {rule_codes} if isinstance(rule_codes, str) else set(rule_codes or ())
    result = {ident: {} for ident in payslips.ids}
    identities = {}
    for ident, slip_id, code, total, rule_id in rows:
        if requested and code not in requested:
            continue
        if code in ('BASIC', 'GROSS', 'NET'):
            if not rule_id:
                raise UserError(_('Original essential payroll rule identity is missing: %s', code))
            key = (slip_id, code)
            identities.setdefault(key, set()).add(rule_id)
            if len(identities[key]) > 1:
                raise UserError(_('Historical %s has multiple rule identities. Resolve the audited reference before exporting this concept.', code))
        codes = result[slip_id]
        codes[code] = codes.get(code, 0.0) + total
    return result


def stored_payslip_totals(payslips, rule_codes=None):
    """Read selected stored totals with complete visibility and rule identity checks."""
    grouped = stored_payslip_code_totals(payslips, rule_codes)
    return {ident: sum(values.values(), 0.0) for ident, values in grouped.items()}
