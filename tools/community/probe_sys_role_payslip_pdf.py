"""Render SyS payroll from the retained operator action on the native or recovered .6.3 QA copy."""
from contextlib import contextmanager
from hashlib import sha256
import json
import importlib
import os
from pathlib import Path
import shutil
import threading
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from lxml import etree, html
from odoo import http
from odoo.exceptions import AccessError
from odoo.addons.web.controllers import report as web_report
from odoo.tests import Form
from werkzeug.serving import make_server
from werkzeug.wrappers import Response


NATIVE = "MANAGEMENT_QA_SYS_REPORT_ROLES_20261126U40RP"
COMMUNITY = "COMMUNITY_SYS_PREVIRED_COHORT_20261127U49E"


@contextmanager
def assets(scope):
    # Both sides run in a network namespace with only its own loopback interface.
    server = make_server("127.0.0.1", 0, http.root, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = "http://127.0.0.1:" + str(server.server_port)
    parameters = type(scope["ir.config_parameter"])
    original = parameters.get_param

    def parameter(records, key, default=False):
        return url if key in ("report.url", "web.base.url") else original(records, key, default)

    try:
        with patch.object(parameters, "get_param", parameter):
            yield
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def private_save(path, data):
    if not isinstance(data, bytes):
        data = json.dumps(data, sort_keys=True, default=str, ensure_ascii=False).encode()
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb") as stream:
        stream.write(data)


def new_confirmed(scope, origin):
    card = Form(scope["hr.payslip"])
    card.date_from, card.date_to = origin.date_from, origin.date_to
    card.employee_id = origin.employee_id
    if card.contract_id != origin.contract_id:
        card.contract_id = origin.contract_id
    if card.struct_id != origin.struct_id:
        card.struct_id = origin.struct_id
    # The original employee onchange proposes the current month. Set the requested month last.
    card.date_from, card.date_to = origin.date_from, origin.date_to
    slip = card.save()
    assert (slip.date_from, slip.date_to) == (origin.date_from, origin.date_to)
    slip.compute_sheet()
    scope.flush_all()
    assert slip.state == "verify" and not slip.move_id
    slip.with_context(payslip_generate_pdf=True).action_payslip_done()
    scope.flush_all()
    assert slip.state == "done" and slip.move_id and slip.move_id != origin.move_id
    return slip


def button_file(scope, slip, button):
    url = urlsplit(button["url"])
    assert url.path == "/print/payslips" and not url.netloc
    args = parse_qs(url.query)
    assert list(args) == ["list_ids"] and args["list_ids"] == [str(slip.id)]
    route, = [r for r in scope["ir.http"].routing_map().iter_rules() if r.rule == url.path]
    assert route.endpoint.routing["auth"] == "user" and route.endpoint.routing["type"] == "http"
    owner = importlib.import_module(route.endpoint.__module__)
    with patch.object(owner, "request", SimpleNamespace(env=scope, make_response=Response)):
        response = route.endpoint(list_ids=args["list_ids"][0])
    return response.get_data()


def community_download(scope, slip, action):
    assert action['type'] == 'ir.actions.report' and action['report_type'] == 'qweb-pdf'
    url = '/report/pdf/' + action['report_name'] + '/' + str(slip.id)
    with patch.object(web_report, 'request', SimpleNamespace(env=scope, make_response=Response)):
        response = web_report.ReportController().report_download(json.dumps([url, action['report_type']]),
                                                                  context=json.dumps(dict(scope.context)))
    assert response.headers['Content-Type'] == 'application/pdf'
    assert response.headers['Content-Disposition'].startswith('attachment;')
    return response.get_data()


def denied_downloads(env, ident, company):
    assert env.cr.dbname == COMMUNITY
    env.cr.rollback()
    env.cr.execute("SET TRANSACTION READ ONLY")
    employee = env['res.users'].browse(6)
    foreign = (employee.company_ids - env['res.company'].browse(company))[:1]
    assert foreign
    public = env.ref('base.public_user')
    tests = ((employee, foreign.id), (public, public.company_id.id))
    for actor, allowed in tests:
        scope = env(user=actor.id,su=False,context={'uid':actor.id,'allowed_company_ids':[allowed]})
        report = scope['ir.actions.report']
        for print_method in (lambda: report._step_original_report_ce_renderer()._get_report_values([ident]),
                             lambda: scope['hr.payslip'].browse(ident)._sys_print_contract_wage()):
            try:
                with scope.cr.savepoint():
                    print_method()
            except AccessError:
                continue
            raise AssertionError('The document or current contract wage was exposed to an unrelated role or company')
    env.cr.rollback()
    return {'scope_combinations_denied':len(tests),'protected_reads_denied':2*len(tests)}


def render(scope, slip, prefix, directory, community):
    slip.check_access("read")
    slip.line_ids.check_access("read")
    action = scope.ref("hr_payroll.action_report_payslip")
    assert action.id == 1431 and action.report_type == "qweb-pdf" and action.model == "hr.payslip"
    assert scope.ref("hr_payroll.menu_hr_payroll_employee_payslips").id in scope["ir.ui.menu"]._visible_menu_ids()
    view = slip.get_view(view_id=5018, view_type="form")
    buttons = etree.fromstring(view["arch"].encode()).xpath("//button")
    print_methods = [(b.get("type"), b.get("name")) for b in buttons if b.get("name") == "action_print_payslip"
                     or b.get("name") == str(action.id)]
    assert ("object", "action_print_payslip") in print_methods
    button = slip.action_print_payslip()
    if button["type"] == "ir.actions.act_url":
        payload = button_file(scope, slip, button)
        assert payload.startswith(b"%PDF-")
        private_save(directory / (prefix + "-button.pdf"), payload)
    elif community:
        payload = community_download(scope, slip, button)
        assert payload.startswith(b'%PDF-')
        private_save(directory / (prefix + '-button.pdf'), payload)
    request = action.report_action(slip, config=False)
    assert request["report_name"] == action.report_name == "hr_payroll.report_payslip_lang"
    scope.cr.execute("""SELECT l.id,l.salary_rule_id,l.code,l.amount,l.quantity,l.rate,l.total,
                           r.appears_on_payslip,s.hide_basic_on_pdf
                        FROM hr_payslip_line l JOIN hr_salary_rule r ON r.id=l.salary_rule_id
                        JOIN hr_payslip p ON p.id=l.slip_id JOIN hr_payroll_structure s ON s.id=p.struct_id
                        WHERE l.slip_id=%s ORDER BY l.sequence,l.id""", (slip.id,))
    rows = scope.cr.fetchall()
    assert rows and len(rows) == len(slip.line_ids)
    visible = [row for row in rows if row[7] and not (row[2] == "BASIC" and row[8])]
    report = scope["ir.actions.report"].with_context(force_report_rendering=True)
    markup, fmt = report._render_qweb_html(request["report_name"], slip.ids)
    doc = html.fromstring(markup)
    assert fmt == "html" and len(doc.xpath("//*[contains(concat(' ',normalize-space(@class),' '),' article ')]")) == 1
    printed = {int(row.get("data-step-line-id")) for row in doc.xpath("//*[@data-step-line-id]")}
    wage_text = doc.xpath('//*[@id="sys_linked_contract_wage"]/span//text()')
    if community:
        values = report._step_original_report_ce_renderer()._get_report_values(slip.ids)
        rendered = values['step_report_lines'](slip)
        assert set(rendered.ids) == {r[0] for r in visible} and printed <= set(rendered.ids)
        assert {line.id: values['step_report_total'](line) for line in rendered} == {r[0]: r[6] for r in visible}
        wage = slip._sys_print_contract_wage()
        assert wage == slip.contract_id.wage and wage_text
        from odoo.tools import format_amount
        assert ' '.join(' '.join(wage_text).split()) == ' '.join(format_amount(scope, wage, slip.company_id.currency_id).split())
    output, fmt = report._render_qweb_pdf(request["report_name"], res_ids=slip.ids)
    assert fmt == "pdf" and output.startswith(b"%PDF-")
    private_save(directory / (prefix + ".pdf"), output)
    private_save(directory / (prefix + ".json"), {
        "linked_wage_printed": bool(wage_text), "rows": rows, "visible": [r[0] for r in visible], "html_ids": sorted(printed),
        "net": next(r[6] for r in rows if r[2] == "NET"),
        "table_text": [[" ".join(cell.itertext()).strip() for cell in tr.xpath("./th|./td")]
                       for tr in doc.xpath("//article//tr|//*[contains(concat(' ',normalize-space(@class),' '),' article ')]//tr")],
    })
    return {"action":action.id, "form":view["id"], "actor":scope.uid, "scope":scope.company.id,
            "buttons":print_methods, "button_type":button["type"], "lines":len(rows), "visible":len(visible),
            "pdf_sha":sha256(output).hexdigest()}


def run(shell, capsule, destination, fresh=False):
    assert shell.cr.dbname in (NATIVE, COMMUNITY)
    community = shell.cr.dbname == COMMUNITY
    directory = Path(destination)
    assert directory.is_dir()
    result = []
    shell.cr.rollback()
    if community:
        m = shell["ir.module.module"].search([("name","=","step_payroll_oca_sys_history"),("state","=","installed")])
        assert m.latest_version == "18.0.1.6.3"
        assert shell["ir.module.module"].search_count([("name","=","step_sys_payslip_print"),("state","=","installed")]) == 1
    slips = sorted({r["slip"] for r in capsule["documents"]})
    expected = {r["attachment"]: r["pdf_sha256"] for r in capsule["documents"]}
    assert len(slips) == 5 and len(expected) == 8
    try:
        with assets(shell):
            for uid in (2, 6):
                scope = shell(user=uid,su=False,context={"uid":uid,"allowed_company_ids":[capsule["company"]],"lang":"es_CL",
                              "mail_notify_force_send":False,"tracking_disable":True})
                assert not scope.su and scope.company.id == capsule["company"]
                for ident in slips[:1] if fresh else slips:
                    shell.cr.rollback()
                    shell.invalidate_all(flush=False)
                    if not fresh:
                        shell.cr.execute("SET TRANSACTION READ ONLY")
                    attachments = scope["ir.attachment"].browse(sorted(expected))
                    attachments.check_access("read")
                    assert {a.id:sha256(a.raw).hexdigest() for a in attachments} == expected
                    origin = scope["hr.payslip"].browse(ident)
                    assert origin.state in ("done","paid")
                    record = new_confirmed(scope, origin) if fresh else origin
                    prefix = ("new" if fresh else "old") + "-%s-%s" % (uid,ident)
                    result.append(render(scope, record, prefix, directory, community))
                    shell.cr.rollback()
                    shell.invalidate_all(flush=False)
        binary = Path(shutil.which("wkhtmltopdf")).resolve(strict=True)
        return {"renderer":sha256(binary.read_bytes()).hexdigest(), "documents":result, "original_attachments":len(expected)}
    finally:
        shell.cr.rollback()
