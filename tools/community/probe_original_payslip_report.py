"""Render HTML and PDF through Cerro's original action on the private pair."""
from hashlib import sha256
import os
from unittest.mock import patch
from uuid import uuid4

from lxml import html
from probe_original_draft_amounts import CASES, capture_ytd, run_case
from probe_original_structure_required import require_private_pair
from probe_original_unmapped_accounting import snapshot

def report_snapshot(env, slip):
    env.flush_all()
    env.cr.execute(
        "SELECT to_jsonb(a) FROM ir_act_report_xml a WHERE id = 462")
    action, = env.cr.fetchone()
    env.cr.execute("SELECT to_jsonb(p) FROM hr_payslip p WHERE id = %s", (slip.id,))
    payroll, = env.cr.fetchone()
    env.cr.execute(
        "SELECT jsonb_agg(to_jsonb(l) ORDER BY id) FROM hr_payslip_line l WHERE slip_id = %s",
        (slip.id,))
    lines, = env.cr.fetchone()
    return action, payroll, lines


def render_pdf(actor, report, slip, output):
    url = os.environ['STEPS_PRIVATE_REPORT_URL']
    parameters = type(actor.env['ir.config_parameter'])
    original = parameters.get_param

    def get_param(records, key, default=False):
        if key in ('report.url', 'web.base.url'):
            return url
        return original(records, key, default)

    with patch.object(parameters, 'get_param', get_param):
        pdf, kind = actor.with_context(force_report_rendering=True)._render_qweb_pdf(
            report['report_name'], res_ids=[slip.id])
    assert kind == 'pdf' and pdf.startswith(b'%PDF-')
    with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
        stream.write(pdf)
    return sha256(pdf).hexdigest()


def run(env, database, pdf_output=None):
    require_private_pair(env, database)
    community = '_HANDOVER_' in database
    before = snapshot(env)
    try:
        case = next(item for item in CASES if item['structure'] == 2)
        slip = run_case(env, case, community, {}, 'STEP_REPORT_' + uuid4().hex)
        journal = slip.struct_id.with_company(slip.company_id).journal_id
        assert journal and not slip.env.su and slip.env.uid == 7
        if community:
            slip.contract_id.sudo().write({'journal_id': journal.id})
        slip.with_context(without_compute_sheet=True).action_payslip_done()
        assert slip.state == 'done'
        amounts = capture_ytd(slip, {})
        counts = snapshot(env)
        stored = report_snapshot(env, slip)
        action = slip.env.ref('hr_payroll.action_report_payslip')
        assert action.id == 462 and action.model == 'hr.payslip'
        assert action.report_type == 'qweb-pdf' and action.binding_model_id.id == 600
        assert not action.attachment and not action.attachment_use
        assert slip.struct_id.report_id == action
        actor = slip.env['ir.actions.report'].with_context(uid=slip.env.uid)
        if community:
            assert actor._step_original_report_ce_renderer() is not None
        report = action.report_action(slip, config=False)
        assert report['report_name'] == action.report_name
        body, kind = actor._render_qweb_html(report['report_name'], [slip.id])
        assert kind == 'html'
        document = html.fromstring(body)
        assert document.xpath('//div[contains(concat(" ",normalize-space(@class)," ")," page ")]')
        assert slip.employee_id.name in ' '.join(document.itertext())
        env.invalidate_all()
        assert snapshot(env) == counts and capture_ytd(slip, {}) == amounts
        assert report_snapshot(env, slip) == stored
        assert slip.state == 'done' and action.id == 462 and slip.struct_id.report_id == action
        result = {'action': action.id, 'operator': slip.env.uid, 'structure': slip.struct_id.id,
                  'presentation': kind, 'document_has_employee': True,
                  'body_sha256': sha256(body).hexdigest()}
        if pdf_output:
            result['pdf_sha256'] = render_pdf(actor, report, slip, pdf_output)
            env.invalidate_all()
            assert snapshot(env) == counts and capture_ytd(slip, {}) == amounts
            assert report_snapshot(env, slip) == stored
    finally:
        env.cr.rollback()
    assert snapshot(env) == before
    return {**result, 'preserved': True, 'rolled_back': True}
