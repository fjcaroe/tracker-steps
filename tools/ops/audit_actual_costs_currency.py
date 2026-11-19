"""Run in a canonical Odoo shell; reconcile USD against the booked Steps ledger.

The transaction is read-only and always rolled back. No entries are posted,
rates changed, users created or messages sent. Output contains counts only.
"""
import json
import re
from odoo import api, SUPERUSER_ID


assert env.cr.dbname in ('LAB_TAREAS', 'CERRO_EL_PLOMO', 'QA-CERROELPLOMO') or re.fullmatch(
    r'MANAGEMENT_QA_(DEVELOPMENT|CERRO|QA-CERRO)_t229_[0-9a-f]{8}(?:_r[1-9][0-9]*)?', env.cr.dbname)
env.cr.rollback()
env.cr.execute('SET TRANSACTION READ ONLY')
try:
    audit = api.Environment(env.cr, SUPERUSER_ID, {})
    usd = audit.ref('base.USD')
    sources = audit['account.move.line'].search([
        ('parent_state', '=', 'posted'), ('operational_currency_id', '=', usd.id),
    ]).filtered(lambda line: isinstance(line.analytic_distribution, dict) and bool(line.analytic_distribution))
    rows = audit['step.management.actual.cost.report'].search([('move_line_id', 'in', sources.ids)])
    totals, unavailable = {}, set()
    for row in rows:
        if not row.usd_available:
            unavailable.add(row.move_line_id.id)
        amounts = totals.setdefault(row.move_line_id.id, [0., 0.])
        amounts[0] += row.debit_usd
        amounts[1] += row.credit_usd
    mismatches = 0
    for source in sources:
        actual = totals.get(source.id)
        if actual is None or any(usd.compare_amounts(a, b) for a, b in zip(
                actual, (source.operational_debit, source.operational_credit))):
            mismatches += 1
    proof = {'database': env.cr.dbname, 'booked_usd_lines': len(sources),
             'allocations': len(rows), 'mismatches': mismatches, 'unavailable': len(unavailable)}
    print('ACTUAL_COSTS_BOOKED_USD_AUDIT ' + json.dumps(proof))
    assert not mismatches and not unavailable, 'Report must match the already-booked operational USD ledger'
    print('ACTUAL_COSTS_BOOKED_USD_AUDIT_OK')
finally:
    env.cr.rollback()
