"""Read-only admission and cache restoration of real, stored payroll history."""
from odoo import _
from odoo.exceptions import UserError

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
