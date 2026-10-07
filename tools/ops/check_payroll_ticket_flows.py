"""Generate from real payslips with a request context; roll back all probe writes.

Execute in Odoo shell with CASES supplied from a private operator JSON file.
This calls the real vendor generator, then the same wizard used by HTTP routes.
It does not submit anything to PreviRed or recompute payroll.
"""
import calendar
import json
from datetime import datetime
from types import SimpleNamespace
from werkzeug.wrappers import Request, Response
from odoo import http
from odoo.addons.step_hr_previred.tools import previred

results = []
try:
    # A live HTTP request initializes inherited @route metadata before dispatch.
    # Odoo shell has no dispatcher; construct that same routing map first.
    env['ir.http'].routing_map()
    for case in CASES:
        key = previred.rut_key(case['rut'])
        employee = env['hr.employee'].with_context(active_test=False).search([('identification_id', '!=', False)]).filtered(
            lambda row: previred.rut_key(row.identification_id) == key)
        assert len(employee) == 1, 'Expected exactly one employee for the private case'
        company = employee.company_id
        scoped = env(context=dict(env.context, allowed_company_ids=company.ids))
        period = datetime.strptime(case['period'], '%m%Y').date()
        first = period.replace(day=1)
        last = period.replace(day=calendar.monthrange(period.year, period.month)[1])
        slips = scoped['hr.payslip'].search([('employee_id', '=', employee.id), ('date_from', '=', first),
                                            ('date_to', '=', last), ('state', 'in', ['verify', 'done', 'paid'])])
        assert slips, 'No eligible payslip for the private case'
        before = [(slip.id, [(line.id, line.total) for line in slip.line_ids],
                   [(line.id, line.number_of_days) for line in slip.worked_days_line_ids]) for slip in slips]
        fake_request = SimpleNamespace(env=scoped, session=SimpleNamespace(db=env.cr.dbname, uid=env.uid, context=scoped.context),
                                       httprequest=Request.from_values(), make_response=lambda data, headers=None, **kw: Response(data, headers=headers))
        http._request_stack.push(fake_request)
        try:
            wizard = scoped['step.previred.export.wizard'].create({'company_id': company.id, 'date_from': first,
                                                                  'date_to': last, 'allow_without_department': True})
            dataset = wizard._build()
        finally:
            http._request_stack.pop()
        records = [record for record in dataset.records if record.employee_id == employee.id]
        assert records, 'Employee absent from canonical export'
        for record in records:
            row = record.principal
            for field, expected in case['fields'].items():
                if isinstance(expected, str) and expected.startswith('rule:'):
                    slip = slips.filtered(lambda item: item.id == record.payslip_id)
                    expected = int(sum(slip.line_ids.filtered(lambda line: line.code == expected[5:]).mapped('total')))
                assert row[int(field)-1] == str(expected), (case['ticket'], field, row[int(field)-1], expected)
        slips.invalidate_recordset()
        after = [(slip.id, [(line.id, line.total) for line in slip.line_ids],
                  [(line.id, line.number_of_days) for line in slip.worked_days_line_ids]) for slip in slips]
        assert before == after, 'Probe changed payroll'
        results.append({'ticket':case['ticket'], 'company_id':company.id,
                        'employee_id':employee.id, 'payslip_ids':slips.ids, 'fields':case['fields'],
                        'corporate_errors':[(issue.code, issue.message) for issue in dataset.errors],
                        'issue_codes': sorted({issue.code for issue in dataset.issues}), 'payroll_preserved': True})
    print('PAYROLL_TICKET_FLOWS ' + json.dumps(results, ensure_ascii=False))
finally:
    env.cr.rollback()
print('PROBE_ROLLBACK_OK')
