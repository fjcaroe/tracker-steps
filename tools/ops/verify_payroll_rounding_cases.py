"""Rehearse private September fixtures only in an isolated destination copy.

Caller supplies CASES: slip_id plus expected GROSS, TOTAL_DSCTOS and NET.
The effective-date predicate is patched only in this clone transaction, so the
actual September inputs/indicators stay applicable. Originals are never saved.
"""
import json
import re
from lxml import html
from unittest.mock import patch

assert env.cr.dbname.startswith('MANAGEMENT_QA_'), 'Never recalculate live payroll'
assert CASES
try:
    results = []
    for case in CASES:
        original = env['hr.payslip'].browse(case['slip_id']).exists()
        assert original and original.date_from.year == 2026 and original.date_from.month == 9
        before = original.line_ids.read(['code','amount','quantity','rate','total'])
        draft = original.with_context(tracking_disable=True,mail_create_nosubscribe=True).copy(
            {'state':'draft','move_id':False})
        with patch.object(type(draft), '_step_clp_rounding_applies', return_value=True):
            draft.compute_sheet()
        values = {line.code:line.total for line in draft.line_ids}
        for code, expected in case['expected'].items():
            assert values[code] == expected, (original.id, code, values[code], expected)
        rendered, _ = env['ir.actions.report']._render_qweb_html('hr_payroll.report_payslip_lang', [draft.id])
        tree = html.fromstring(rendered)
        amounts = {int(re.sub(r'[^0-9-]', '', node.text_content()))
                   for node in tree.xpath("//span[contains(@class,'oe_currency_value')]")
                   if re.sub(r'[^0-9-]', '', node.text_content()).lstrip('-').isdigit()}
        assert all(value in amounts for value in case['expected'].values()), 'Report totals differ from lines'
        assert original.line_ids.read(['code','amount','quantity','rate','total']) == before
        results.append({'source_slip_id':original.id,'totals':{k:values[k] for k in case['expected']},
                        'full_compute_sheet':True,'native_report_totals':True,'original_unchanged':True})
    print('PAYROLL_ROUNDING_CASES_OK '+json.dumps(results))
finally:
    env.cr.rollback()
