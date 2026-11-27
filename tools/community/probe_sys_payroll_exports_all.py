"""Compare private SyS payroll exports by real company, period and authenticated operator."""

import base64
from calendar import monthrange
from collections import Counter
import csv
from dataclasses import asdict
import hashlib
import hmac
import io
import json
from types import SimpleNamespace
from unittest.mock import patch

from odoo import api
from odoo.exceptions import AccessError, UserError
from odoo.http import Response, _request_stack
from werkzeug.exceptions import HTTPException
from psycopg2 import sql
from odoo.addons.step_hr_previred.tools import previred


DATABASES = ('MANAGEMENT_QA_SYS_PREVIRED_20261126U40N', 'COMMUNITY_SYS_PREVIRED_COHORT_20261126U40I',
             'COMMUNITY_SYS_PREVIRED_COHORT_20261126U40J')
TABLES = ('resource_calendar','resource_calendar_attendance','hr_employee', 'hr_payslip', 'hr_payslip_line', 'hr_payslip_input', 'hr_payslip_worked_days',
          'hr_contract', 'hr_payslip_run', 'account_move', 'account_move_line', 'ir_sequence', 'ir_sequence_date_range',
          'step_previred_batch', 'step_previred_batch_file', 'step_previred_export_wizard')


def seal(key, value):
    payload = json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode()
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def snapshot(shell):
    with shell.registry.cursor() as cr:
        cr.execute('SET TRANSACTION READ ONLY')
        result = {}
        for table in TABLES:
            cr.execute(sql.SQL("SELECT count(*),md5(string_agg(md5(to_jsonb(t)::text),'' ORDER BY id)) FROM {} t")
                       .format(sql.Identifier(table)))
            result[table] = cr.fetchone()
        return result


def file_receipt(raw, rows, columns, key):
    assert all(len(row) == columns for row in rows)
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'rows': len(rows), 'columns': columns,
            'row_multiset': seal(key, sorted(seal(key, row) for row in rows)),
            'by_column': [seal(key, [row[i] for row in rows]) for i in range(columns)]}


def closed_scope(shell):
    shell.cr.execute("""WITH closed AS (
            SELECT company_id, date_trunc('month',date_from)::date period, id
            FROM hr_payslip WHERE state IN ('done','paid')
        ), latest AS (SELECT company_id,max(period) period FROM closed GROUP BY company_id)
        SELECT c.company_id,c.period,array_agg(c.id ORDER BY c.id)
        FROM closed c JOIN latest USING(company_id,period) GROUP BY c.company_id,c.period ORDER BY c.company_id""")
    rows = shell.cr.fetchall()
    counts = Counter()
    for _, start, ids in rows:
        counts[start.isoformat()] += len(ids)
    if len(rows) != 12 or counts != {'2026-07-01': 3, '2026-10-01': 130}:
        raise ValueError('The private original SyS latest closed census differs from the reference')
    return rows


def checked_slips(env, ids):
    slips = env['hr.payslip'].browse(ids)
    slips.check_access('read')
    assert set(slips.company_id.ids) == {env.company.id}
    employees = slips.mapped('employee_id')
    employees.check_access('read')
    employees.check_field_access_rights('read', ['identification_id'])
    env.cr.execute('SELECT id FROM hr_payslip_line WHERE slip_id=ANY(%s)', (slips.ids,))
    env['hr.payslip.line'].browse([i for i, in env.cr.fetchall()]).check_access('read')
    return slips


def book(env, req, route, start, end, slips, key):
    from odoo.addons.l10n_cl_simpledigital_payroll.controllers import libro_remuneraciones
    def download(header):
        res = route.endpoint(date_from=start.isoformat(), date_to=end.isoformat(),
                             include_header=str(header), company_id=env.company.id)
        if res.status_code != 200 or res.mimetype != 'text/csv':
            return {'status':'http_response','code':res.status_code,'mimetype':res.mimetype,
                    'response_sha256':hashlib.sha256(res.get_data()).hexdigest()}, []
        assert 'windows-1252' in res.headers['Content-Type']
        raw = res.get_data()
        assert len(raw) == int(res.headers['Content-Length'])
        return raw, list(csv.reader(io.StringIO(raw.decode('cp1252')), delimiter=';'))
    with patch.object(libro_remuneraciones, 'request', req):
        raw, rows = download(True)
        if isinstance(raw, dict):
            return raw
        plain, lines = download(False)
    assert isinstance(plain, bytes) and rows and lines == rows[1:]
    header = rows[0]
    assert len(header) == 147
    worker, = [i for i, title in enumerate(header) if title.endswith('(1101)')]
    def rut_key(rut):
        return (rut or '').strip().replace('.', '').replace('-', '').upper()
    produced = Counter(rut_key(row[worker]) for row in lines)
    original = Counter(rut_key(s.employee_id.identification_id) for s in slips)
    return {'status':'generated','file':file_receipt(raw, lines, len(header), key),
            'without_header_sha256':hashlib.sha256(plain).hexdigest(), 'header':seal(key, header),
            'source_identities':sum(original.values()),'identity_matches':sum((produced & original).values()),
            'extra_identities':sum((produced - original).values()),'omitted_identities':sum((original - produced).values())}


def txt(env, start, end, slips, key):
    if not env.user.has_group('step_hr_previred.group_previred_generate'):
        return {'status':'no_generation_role'}
    wiz = env['step.previred.export.wizard'].create(dict(company_id=env.company.id, date_from=start,
        date_to=end, allow_without_department=True, scope='consolidated', output='txt'))
    dataset = wiz._build()
    diagnostic = [asdict(issue) for issue in dataset.issues]
    records = sorted([(r.payslip_id or 0, r.employee_id or 0, r.contract_id or 0) for r in dataset.records])
    ids = {ident for ident, _, _ in records if ident}
    assert ids.issubset(set(slips.ids))
    result = {'spec':dataset.spec_version, 'issues':dict(Counter(i.code for i in dataset.issues)),
              'diagnostics':seal(key, diagnostic),'diagnostic_count':len(diagnostic),
              'diagnostic_multiset':seal(key, sorted(seal(key, entry) for entry in diagnostic)),
              'eligible':dataset.eligible_payslip_count, 'dropped':dataset.dropped_count,
              'principals':len(records),'annexes':dataset.annex_count,'mapped_source_slips':len(ids),
              'source_ids':seal(key, records), 'missing_source_count':len(set(slips.ids) - ids),
              'dataset_rows':seal(key, [row for r in dataset.records for row in r.rows])}
    wiz.action_validate()
    assert wiz.state == 'preview' and not wiz.file_data
    result['validation_screen'] = seal(key, str(wiz.summary_html))
    try:
        wiz.action_generate()
    except (UserError, HTTPException) as exc:
        result.update(refusal(exc, key))
        return result
    result['generation_screen'] = seal(key, str(wiz.summary_html))
    if dataset.errors:
        assert not wiz.file_data and wiz.state == 'preview'
        return dict(result, status='validation_blocked')
    assert wiz.state == 'done' and wiz.batch_id.result == 'ok' and wiz.file_name.endswith('.txt')
    raw = base64.b64decode(wiz.file_data)
    rows = [line.split(';') for line in raw.decode(previred.ENCODING).splitlines()]
    assert len(rows) == dataset.row_count
    return dict(result, status='generated', file=file_receipt(raw, rows, previred.FIELD_COUNT, key))


def refusal(exc, key):
    return {'status':'denied' if isinstance(exc, AccessError) or getattr(exc, 'code', None) in (401,403)
            else 'refused', 'exception':type(exc).__name__,'diagnostic':seal(key,str(exc))}


def run(shell, key, report_progress=None):
    upgrades = {"COMMUNITY_SYS_PREVIRED_MODULES_20261127U41M", "COMMUNITY_SYS_PREVIRED_MODULES_20261127U41MP"}
    if shell.cr.dbname not in (*DATABASES, *upgrades) or not isinstance(key, bytes) or len(key) != 32:
        raise ValueError('Use the exact isolated SyS databases and a shared private comparison key')
    routes = [r for r in shell['ir.http'].routing_map().iter_rules() if r.endpoint.__name__ == 'export_libro_remuneraciones_csv']
    route, = routes
    assert route.endpoint.routing['auth'] == 'user' and route.endpoint.routing['type'] == 'http'
    before = snapshot(shell)
    latest = closed_scope(shell)
    enterprise = shell['ir.module.module'].search_count([('license','=','OEEL-1'),('state','=','installed')])
    assert bool(enterprise) == (shell.cr.dbname == DATABASES[0])
    results = []
    for company, start, ids in latest:
        end = start.replace(day=monthrange(start.year, start.month)[1])
        shell.cr.execute("""SELECT u.id FROM res_users u JOIN res_company_users_rel x ON x.user_id=u.id
                          WHERE x.cid=%s AND u.active AND NOT u.share AND u.id>1 ORDER BY u.id""",(company,))
        uids = [uid for uid, in shell.cr.fetchall()]
        item = {'company':company,'period':start.isoformat(),'closed':len(ids),
                'closed_ids':seal(key,ids),'operators':[]}
        for uid in uids:
            with shell.registry.cursor() as cr:
                try:
                    env = api.Environment(cr,uid,dict(uid=uid,lang='es_CL',allowed_company_ids=[company]))
                    assert not env.su and env.company.id == company and company in env.user.company_ids.ids
                    actor = {'uid':uid}
                    if not env.user.has_group('hr_payroll.group_hr_payroll_manager'):
                        actor.update(book={'status':'no_manager_role'},previred={'status':'no_manager_role'})
                    else:
                        req = SimpleNamespace(env=env, make_response=Response, update_env=lambda **kw: None)
                        _request_stack.push(req)
                        try:
                            for name, operation in [('book',book),('previred',txt)]:
                                try:
                                    with cr.savepoint():
                                        slips = checked_slips(env, ids)
                                        if name == 'book':
                                            actor[name] = operation(env, req, route, start, end, slips, key)
                                        else:
                                            actor[name] = operation(env, start, end, slips, key)
                                except (UserError, HTTPException) as exc:
                                    actor[name] = refusal(exc, key)
                        finally:
                            _request_stack.pop()
                    item['operators'].append(actor)
                finally:
                    cr.rollback()
        results.append(item)
        if report_progress:
            report_progress(item)
    assert snapshot(shell) == before
    return {'database':shell.cr.dbname,'enterprise':enterprise,'latest':results,'originals_preserved':True}
