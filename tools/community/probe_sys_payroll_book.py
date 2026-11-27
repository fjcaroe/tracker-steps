"""Exercise the October SyS book on a private Odoo registry using stored payroll.

Supply the UID and company from the verified v98 reference to probe(). The
caller starts the shell offline. Only receipt hashes and counts leave the probe.
"""
import csv
import hashlib
import io
import json
import re
from types import SimpleNamespace
from unittest.mock import patch

from odoo import api
from odoo.http import Response, _request_stack


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def capture(env, company_id):
    from odoo.addons.l10n_cl_simpledigital_payroll.controllers import libro_remuneraciones

    modules = env['ir.module.module'].sudo().search([('state', '=', 'installed')])
    enterprise = len(modules.filtered(lambda mod: mod.license == 'OEEL-1'))
    community = env.cr.dbname.startswith('COMMUNITY_SYS_PREVIRED_') or env.cr.dbname == 'COMMUNITY_SYS_FINAL_RESTORED_20261127U46R'
    if community:
        assert not enterprise and 'payroll' in modules.mapped('name')
        from odoo.addons.step_payroll_contracts.access import has_payroll_role
        assert has_payroll_role(env, 'manager')
    else:
        assert enterprise and env.user.has_group('hr_payroll.group_hr_payroll_manager')
    assert not env.su and env.company.id == company_id and env.company in env.user.company_ids
    env.cr.execute("""
        SELECT p.id, e.identification_id,
               (SELECT sum(l.total) FROM hr_payslip_line l WHERE l.slip_id=p.id AND l.code='BASIC'),
               (SELECT sum(l.total) FROM hr_payslip_line l WHERE l.slip_id=p.id AND l.code='NET'),
               p.move_id
          FROM hr_payslip p JOIN hr_employee e ON e.id=p.employee_id
         WHERE p.company_id=%s AND p.date_from >= '2026-10-01' AND p.date_to <= '2026-10-31'
           AND p.state IN ('done','paid') ORDER BY p.id
    """, [company_id])
    cohort = env.cr.fetchall()
    assert len(cohort) == 5 and all(row[1] and row[2] is not None and row[3] is not None for row in cohort)
    slips = env['hr.payslip'].browse([row[0] for row in cohort])
    slips.check_access('read')
    slips.mapped('employee_id').check_access('read')
    env.cr.execute("SELECT id FROM hr_payslip_line WHERE slip_id=ANY(%s)", [slips.ids])
    env['hr.payslip.line'].browse([r[0] for r in env.cr.fetchall()]).check_access('read')

    route, = [rule for rule in env['ir.http'].routing_map().iter_rules()
              if rule.endpoint.__name__ == 'export_libro_remuneraciones_csv']
    assert route.endpoint.routing['auth'] == 'user' and route.endpoint.routing['type'] == 'http'
    req = SimpleNamespace(env=env, make_response=Response)
    def download(header):
        res = route.endpoint(date_from='2026-10-01', date_to='2026-10-31',
                             include_header=str(header), company_id=company_id)
        assert res.mimetype == 'text/csv' and res.headers['Content-Disposition'].startswith('attachment;')
        assert 'windows-1252' in res.headers['Content-Type']
        raw = res.get_data()
        assert len(raw) == int(res.headers['Content-Length'])
        return raw, list(csv.reader(io.StringIO(raw.decode('cp1252')), delimiter=';'))

    _request_stack.push(req)
    try:
        with patch.object(libro_remuneraciones, 'request', req):
            raw, rows = download(True)
            assert download(False)[1] == rows[1:]
    finally:
        _request_stack.pop()

    header, *rows = rows
    assert len(header) >= 140 and len(rows) == len(cohort) and all(len(row) == len(header) for row in rows)
    def index(code):
        position, = [i for i, title in enumerate(header) if title.endswith('(' + code + ')')]
        return position
    def rut_key(rut):
        return rut.strip().replace('.', '').replace('-', '').upper()
    worker, basic, earnings, deductions, net = map(index, ('1101', '2101', '5201', '5301', '5501'))
    reported = {rut_key(row[worker]): row for row in rows}
    assert len(reported) == len(rows) and set(reported) == {rut_key(row[1]) for row in cohort}
    assert all(int(reported[rut_key(rut)][basic]) == amount for _, rut, amount, _, _ in cohort)
    assert all(int(row[net]) == int(row[earnings]) - int(row[deductions]) for row in rows)
    net_matches = sum(int(reported[rut_key(rut)][net]) == amount for _, rut, _, amount, _ in cohort)
    moves = sorted({r[4] for r in cohort if r[4]})
    env.cr.execute("""
        SELECT m.id,m.company_id,m.journal_id,m.state,count(l.id),
               coalesce(sum(l.debit),0)::text,coalesce(sum(l.credit),0)::text
        FROM account_move m LEFT JOIN account_move_line l ON l.move_id=m.id
        WHERE m.id=ANY(%s) GROUP BY m.id ORDER BY m.id
    """, [moves])
    ledger = env.cr.fetchall()
    assert [r[0] for r in ledger] == moves
    return {'community': community, 'enterprise': enterprise, 'operator': env.uid, 'company': company_id,
            'period': '2026-10', 'rows': len(rows), 'columns': len(header), 'csv_sha256': sha(raw),
            'stored_basic_matches': len(rows), 'stored_net_matches': net_matches,
            'net_equals_reported_earnings_minus_deductions': len(rows),
            'linked_moves': len(ledger), 'journal_items': sum(r[4] for r in ledger),
            'ledger_sha256': sha(json.dumps(ledger, separators=(',', ':')).encode())}


def probe(shell_env, company_id, uid):
    assert (shell_env.cr.dbname == 'COMMUNITY_SYS_FINAL_RESTORED_20261127U46R' or
            re.fullmatch(r'(?:MANAGEMENT_QA_SYS_PREVIRED_|COMMUNITY_SYS_PREVIRED_)[A-Z0-9_]+', shell_env.cr.dbname))
    assert type(uid) is int and uid > 1 and type(company_id) is int and company_id > 0
    with shell_env.registry.cursor() as cursor:
        cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        cursor.execute("SELECT current_setting('transaction_read_only'),current_database()")
        assert cursor.fetchone() == ('on', shell_env.cr.dbname)
        return capture(api.Environment(cursor, uid, {'allowed_company_ids': [company_id], 'lang': 'es_CL'}), company_id)
