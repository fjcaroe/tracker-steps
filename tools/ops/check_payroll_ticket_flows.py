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
        period = datetime.strptime(case['period'], '%m%Y').date()
        first = period.replace(day=1)
        last = period.replace(day=calendar.monthrange(period.year, period.month)[1])
        key = previred.rut_key(case['rut'])
        employee_domain = [('identification_id', '!=', False)]
        if case.get('company_id'):
            employee_domain.append(('company_id', '=', case['company_id']))
        employee = env['hr.employee'].with_context(active_test=False).search(employee_domain).filtered(
            lambda row: previred.rut_key(row.identification_id) == key)
        if len(employee) > 1:
            eligible_domain = [
                ('employee_id', 'in', employee.ids), ('date_from', '=', first),
                ('date_to', '=', last), ('state', 'in', ['verify', 'done', 'paid'])]
            if case.get('payslip_ids'):
                eligible_domain.append(('id', 'in', case['payslip_ids']))
            eligible = env['hr.payslip'].search(eligible_domain)
            employee &= eligible.employee_id
        assert len(employee) == 1, ('Expected exactly one employee for the private case',
                                    case['rut'], employee.ids)
        company = employee.company_id
        scoped = env(context=dict(env.context, allowed_company_ids=company.ids))
        slips = scoped['hr.payslip'].search([('employee_id', '=', employee.id), ('date_from', '=', first),
                                            ('date_to', '=', last), ('state', 'in', ['verify', 'done', 'paid'])])
        if case.get('payslip_ids'):
            slips = slips.filtered(lambda slip: slip.id in case['payslip_ids'])
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
            if case.get('verify_download'):
                import base64
                wizard.action_generate()
                assert wizard.state == 'done' and wizard.file_data, 'Canonical TXT generation was blocked'
                payload = base64.b64decode(wizard.file_data)
                downloaded = [line.split(';') for line in payload.decode(previred.ENCODING).strip().splitlines()]
                assert downloaded and all(len(row) == 105 for row in downloaded)
                target = [row for row in downloaded
                          if previred.rut_key(row[0] + row[1]) == key
                          and previred.normalize_line_type(row[13]) == previred.LINE_PRINCIPAL]
                assert len(target) == 1, 'Expected one reported principal in the actual download'
                for position, expected in case['fields'].items():
                    if not str(expected).startswith('rule:'):
                        assert target[0][int(position)-1] == str(expected), ('download', position)
                wizard.output = 'xlsx'
                wizard.action_generate()
                assert wizard.state == 'done' and base64.b64decode(wizard.file_data).startswith(b'PK')
        finally:
            http._request_stack.pop()
        records = [record for record in dataset.records
                   if record.employee_id == employee.id and record.payslip_id in slips.ids]
        assert records, 'Employee absent from canonical export'
        for record in records:
            row = record.principal
            for code in case.get('annex_codes_without_end', []):
                matching = [annex for annex in record.annexes
                            if str(annex[14]).lstrip('0') == str(code)]
                assert matching, ('Reported open-ended annex missing', code)
                assert all(str(annex[16] or '').strip() in previred.NULL_DATE_TOKENS
                           for annex in matching)
            for field, expected in case['fields'].items():
                if isinstance(expected, str) and expected.startswith('rule:'):
                    slip = slips.filtered(lambda item: item.id == record.payslip_id)
                    expected = int(sum(slip.line_ids.filtered(lambda line: line.code == expected[5:]).mapped('total')))
                assert row[int(field)-1] == str(expected), (case['ticket'], field, row[int(field)-1], expected)
            for annex in record.annexes:
                for field, expected in case.get('annex_fields', {}).items():
                    assert annex[int(field)-1] == str(expected), (
                        case['ticket'], 'annex', field, annex[int(field)-1], expected)
        slips.invalidate_recordset()
        after = [(slip.id, [(line.id, line.total) for line in slip.line_ids],
                  [(line.id, line.number_of_days) for line in slip.worked_days_line_ids]) for slip in slips]
        assert before == after, 'Probe changed payroll'
        results.append({'ticket':case['ticket'], 'company_id':company.id,
                        'employee_id':employee.id, 'payslip_ids':slips.ids, 'fields':case['fields'],
                        'corporate_errors':[(issue.code, issue.message) for issue in dataset.errors],
                        'issue_codes': sorted({issue.code for issue in dataset.issues}),
                        'download_verified': bool(case.get('verify_download')), 'payroll_preserved': True})
    print('PAYROLL_TICKET_FLOWS ' + json.dumps(results, ensure_ascii=False))
finally:
    env.cr.rollback()
print('PROBE_ROLLBACK_OK')
