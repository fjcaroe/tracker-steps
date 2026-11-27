"""Render five closed SyS payslips through their original action in a private derivative."""

from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import re

from lxml import html
from odoo import api
from odoo.modules.module import get_manifest
from psycopg2 import sql

from probe_original_payslip_report import render_pdf

INTEGRATED_COHORTS = ('COMMUNITY_SYS_PREVIRED_COHORT_20261126U40I', 'COMMUNITY_SYS_PREVIRED_COHORT_20261126U40J')
REPORT_MODULES = {'step_simpledigital_oca_base': '18.0.1.7.3', 'step_payroll_original_report': '18.0.1.0.2'}


def historical_snapshot(env, action_id):
    result = {}
    for table in ('hr_payslip', 'hr_payslip_line', 'hr_payslip_input', 'hr_payslip_worked_days',
                  'hr_salary_rule', 'hr_contract'):
        env.cr.execute(sql.SQL("SELECT count(*),md5(string_agg(to_jsonb(t)::text,'|' ORDER BY id)) FROM {} t")
                       .format(sql.Identifier(table)))
        result[table] = env.cr.fetchone()
    env.cr.execute('SELECT md5(to_jsonb(a)::text) FROM ir_act_report_xml a WHERE id=%s', (action_id,))
    result['action'] = env.cr.fetchone()
    env.cr.execute("SELECT count(*),md5(string_agg(to_jsonb(a)::text,'|' ORDER BY id)) FROM ir_attachment a "
                   "WHERE res_model='hr.payslip' AND mimetype='application/pdf'")
    result['archives'] = env.cr.fetchone()
    return result


def amount_text(value):
    value = re.sub(r'[^\d-]', '', value)
    return Decimal(value) if value else None


def archived(env, capsule):
    rows = capsule['documents']
    expected = {row['attachment']: row['pdf_sha256'] for row in rows}
    records = env['ir.attachment'].browse(sorted(expected))
    records.check_access('read')
    records.check_field_access_rights('read', ['res_model', 'res_id', 'mimetype', 'raw'])
    assert len(expected) == 8
    actual = {record.id: sha256(record.raw).hexdigest() for record in records}
    assert all(record.res_model == 'hr.payslip' and record.mimetype == 'application/pdf' for record in records)
    assert actual == expected
    return actual


def run(shell_env, capsule, directory, action_id):
    integrated = shell_env.cr.dbname in INTEGRATED_COHORTS
    if not integrated and not re.fullmatch(r'COMMUNITY_SYS_(?:STORED_REPORT|REPORT_ROLES)_[A-Z0-9_]+', shell_env.cr.dbname):
        raise ValueError('A private restored SyS reporting derivative is required')
    assert capsule['period'] == '2026-10'
    company, uid = capsule['company'], capsule['uid']
    env = api.Environment(shell_env.cr, uid, {'allowed_company_ids': [company], 'lang': 'es_CL', 'uid': uid})
    base = historical_snapshot(env, action_id)
    versions = {}
    for name, expected in REPORT_MODULES.items():
        module = shell_env['ir.module.module'].search([('name', '=', name), ('state', '=', 'installed')])
        module.ensure_one()
        versions[name] = {'database': module.latest_version, 'package': get_manifest(name)['version']}
        if integrated:
            assert set(versions[name].values()) == {expected}, 'Integrated report version mismatch: ' + name
    assert env.company.id == company and not env.su and env.company.currency_id.decimal_places == 0
    original_pdfs = archived(env, capsule)
    action = env.ref('hr_payroll.action_report_payslip')
    assert action.id == action_id and action.model == 'hr.payslip' and action.report_type == 'qweb-pdf'
    assert action.report_name == 'hr_payroll.report_payslip_lang' and not action.attachment_use and not action.attachment
    env.cr.execute("""SELECT id FROM hr_payslip WHERE company_id=%s AND date_from='2026-10-01'
                      AND date_to='2026-10-31' AND state IN ('done','paid') ORDER BY id""", (company,))
    slips = env['hr.payslip'].browse([r[0] for r in env.cr.fetchall()])
    assert len(slips) == 5 and set(slips.ids) == {r['slip'] for r in capsule['documents']}
    slips.check_access('read')
    report_model = env['ir.actions.report']
    assert report_model._step_original_report_ce_renderer() is not None
    output = Path(directory)
    assert output.is_dir()
    receipts = []
    for slip in slips:
        # No action, formula, or line is created or recomputed by the probe.
        env.cr.execute("""SELECT l.id,l.code,l.total,r.appears_on_payslip,s.hide_basic_on_pdf
            FROM hr_payslip_line l JOIN hr_salary_rule r ON r.id=l.salary_rule_id
            JOIN hr_payslip p ON p.id=l.slip_id JOIN hr_payroll_structure s ON s.id=p.struct_id
            WHERE l.slip_id=%s ORDER BY l.sequence,l.id""", (slip.id,))
        rows = env.cr.fetchall()
        assert rows and len(rows) == len(slip.line_ids)
        printed = {ident: amount for ident, code, amount, visible, hidden_basic in rows
                   if visible and not (hidden_basic and code == 'BASIC')}
        net, = [Decimal(str(amount)) for _, code, amount, _, _ in rows if code == 'NET']
        assert all(Decimal(row['totals']['NET']) == net for row in capsule['documents'] if row['slip'] == slip.id)
        request = action.report_action(slip, config=False)
        assert request['report_name'] == action.report_name
        raw, kind = report_model._render_qweb_html(request['report_name'], slip.ids)
        assert kind == 'html'
        page = html.fromstring(raw)
        summary = page.xpath('//*[@id="to_pay"]')
        assert len(summary) == 1 and 'Líquido a recibir' in summary[0].text_content()
        assert amount_text(summary[0].text_content()) == net
        visible_rows = page.xpath('//*[@data-step-line-id]')
        ids = [int(row.get('data-step-line-id')) for row in visible_rows]
        assert sorted(ids) == sorted(printed), 'Printed rows differ from the original visible source rows'
        for ident, row in zip(ids, visible_rows):
            last, = row.xpath('./td[last()]')
            value = printed[ident]
            assert amount_text(last.text_content()) == (None if value is None else Decimal(str(value)))
        assert slip.employee_id.name in ' '.join(page.itertext())
        path = output / f'{slip.id}.pdf'
        digest = render_pdf(report_model, request, slip, str(path))
        receipts.append({'slip': slip.id, 'visible_rows': len(ids), 'stored_lines': len(rows),
                         'html_net_matches_stored': True, 'printed_ids_and_amounts_verified': True, 'pdf_sha256': digest})
    assert archived(env, capsule) == original_pdfs
    env.cr.rollback()
    assert historical_snapshot(env, action_id) == base
    return {'action': action.id, 'uid': uid, 'slips': receipts, 'versions': versions,
            'historical_tables_preserved': True, 'eight_archived_pdf_bytes_unchanged': True}
