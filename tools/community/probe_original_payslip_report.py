"""Render HTML through Cerro's original payslip action on the private pair."""
from hashlib import sha256
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


def run(env, database):
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
                  'presentation': kind, 'document_has_employee': True, 'body_sha256': sha256(body).hexdigest()}
    finally:
        env.cr.rollback()
    assert snapshot(env) == before
    return {**result, 'preserved': True, 'rolled_back': True}
