"""Admission of original stored annual snapshots; never reconstruct closed YTD."""
from odoo import _
from odoo.exceptions import UserError
from .history import columns, protected_sql


def assert_ytd_snapshots(cr):
    names=columns(cr,'hr_payslip')
    if not names or not columns(cr,'hr_payslip_line'):return
    source='hr_payslip_line l JOIN hr_payslip s ON s.id=l.slip_id'
    predicate=protected_sql(names)
    cr.execute('SELECT 1 FROM '+source+' WHERE '+predicate+' LIMIT 1')
    if not cr.fetchone():return
    if 'ytd' not in columns(cr,'hr_payslip_line'):
        raise UserError(_('Adopt original stored YTD snapshots before upgrading closed payroll.'))
    cr.execute('SELECT 1 FROM '+source+' WHERE '+predicate+' AND l.ytd IS NULL LIMIT 1')
    if cr.fetchone():raise UserError(_('Original closed YTD snapshots are incomplete.'))
