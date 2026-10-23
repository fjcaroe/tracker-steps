"""Rehearse private September fixtures only in an isolated destination copy.

Caller supplies CASES: slip_id plus expected GROSS, TOTAL_DSCTOS and NET.
The effective-date predicate is patched only in this clone transaction, so the
actual September inputs/indicators stay applicable. Contract review is confirmed
through its normal action only in the clone, and every change is rolled back.
Original payslip lines are never saved.
"""
import json
import re
from lxml import html
from unittest.mock import patch
from odoo.tools import config

assert env.cr.dbname.startswith('MANAGEMENT_QA_'), 'Never recalculate live payroll'
assert CASES
try:
    results = []
    for case in CASES:
        original = env['hr.payslip'].browse(case['slip_id']).exists()
        assert original and original.date_from.year == 2026 and original.date_from.month == 9
        users = env['res.users'].search([('active','=',True),('share','=',False),('id','!=',1),
            ('company_ids','in',original.company_id.ids)]).filtered(
                lambda user: user.has_group('hr_payroll.group_hr_payroll_manager'))
        assert users, 'An existing payroll manager for the case company is required'
        scoped = env(user=users[:1],su=False,context=dict(env.context,allowed_company_ids=original.company_id.ids))
        original = scoped['hr.payslip'].browse(original.id)
        before = original.line_ids.read(['code','amount','quantity','rate','total'])
        draft = original.with_context(tracking_disable=True,mail_create_nosubscribe=True).copy(
            {'state':'draft','move_id':False,'line_ids':False})
        if draft.contract_id.step_payroll_migration_review:
            draft.contract_id.action_confirm_payroll_migration()
        with patch.object(type(draft), '_step_clp_rounding_applies', return_value=True):
            draft.compute_sheet()
        previous=config['test_enable'];config['test_enable']=True
        try:
            from odoo.tests import Form
        finally:
            config['test_enable']=previous
        Form(draft)
        values = {line.code:line.total for line in draft.line_ids}
        for code, expected in case['expected'].items():
            assert values[code] == expected, (original.id, code, values[code], expected)
        rendered, _ = scoped['ir.actions.report']._render_qweb_html('hr_payroll.report_payslip_lang', [draft.id])
        tree = html.fromstring(rendered)
        amounts = {int(re.sub(r'[^0-9-]', '', node.text_content()))
                   for node in tree.xpath("//span[contains(@class,'oe_currency_value')]")
                   if re.sub(r'[^0-9-]', '', node.text_content()).lstrip('-').isdigit()}
        assert all(value in amounts for value in case['expected'].values()), 'Report totals differ from lines'
        assert original.line_ids.read(['code','amount','quantity','rate','total']) == before
        results.append({'source_slip_id':original.id,'company_id':original.company_id.id,'existing_profile':scoped.uid,'totals':{k:values[k] for k in case['expected']},
                        'full_compute_sheet':True,'native_report_totals':True,'original_unchanged':True})
    print('PAYROLL_ROUNDING_CASES_OK '+json.dumps(results))
finally:
    env.cr.rollback()
