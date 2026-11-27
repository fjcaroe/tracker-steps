"""Exercise a single historical payslip PDF through payroll, its library folder and the authenticated portal."""
import hashlib
from pathlib import Path
from urllib.parse import quote, urlsplit

from lxml import etree
from odoo.exceptions import AccessError

from probe_document_portal_http import COMBINED, individual, session


def intersection(env, actor):
    companies = actor.company_ids.filtered("active")
    env.cr.execute("""
        SELECT d.id,a.id,p.id,p.company_id FROM documents_document d
          JOIN ir_attachment a ON a.id=d.attachment_id
          JOIN hr_payslip p ON a.res_model='hr.payslip' AND p.id=a.res_id
         WHERE d.res_model='hr.payslip' AND d.res_id=p.id AND d.active AND d.type='binary'
               AND d.access_via_link='none' AND d.company_id=p.company_id AND p.company_id=ANY(%s)
               AND a.public IS NOT TRUE AND a.res_field IS NULL AND a.mimetype='application/pdf' AND a.file_size>0
         ORDER BY d.id
    """, [companies.ids])
    rows = env.cr.fetchall()
    assert rows
    for doc_id, file_id, slip_id, company in rows:
        scope = env(user=actor.id, su=False, context={"allowed_company_ids": [company], "bin_size": False,
                    "tracking_disable": True, "mail_notify_force_send": False})
        slip = scope["hr.payslip"].browse(slip_id)
        doc = scope["documents.document"].browse(doc_id)
        if not slip.has_access("read") or not doc.has_access("write") or not doc.may_manage_access:
            continue
        attachment = scope["ir.attachment"].browse(file_id)
        try:
            attachment.check("read")
        except AccessError:
            continue
        for company2 in companies.ids:
            if company2 == company:
                continue
            away = env(user=actor.id, su=False, context={"allowed_company_ids": [company2]})
            if away["hr.payslip"].browse(slip_id).has_access("read"):
                continue
            try:
                away["ir.attachment"].browse(file_id).check("read")
            except AccessError:
                return slip, doc, attachment, len(rows)
    raise AssertionError("No shared original PDF with authorized manager and excluded company")


def combined(env, prepared):
    allowed = (COMBINED, 'COMMUNITY_SYS_PREVIRED_MODULES_20261127U44FD')
    assert env.cr.dbname in allowed and env.registry.test_cr is None
    assert {line.split(":")[0].strip() for line in Path("/proc/net/dev").read_text().splitlines()[2:]} == {"lo"}
    manager = env["res.users"].browse(6)
    assert manager.active and not manager.share and manager.has_group("payroll.group_payroll_manager")
    slip, doc, attachment, eligible = intersection(env, manager)
    scope = doc.env
    assert not scope.su and doc.attachment_id == attachment and attachment.res_id == slip.id
    assert slip.read(["id"])[0]["id"] == slip.id
    payroll_form = etree.fromstring(slip.get_view(view_type="form")["arch"].encode())
    assert payroll_form.xpath("//field[@name='employee_id']") and payroll_form.xpath("//field[@name='date_from']")
    menu = scope.ref("documents.dashboard")
    assert menu.id in scope["ir.ui.menu"]._visible_menu_ids() and menu.action == scope.ref("step_document_library.action_library")
    form = doc.get_view(view_id=scope.ref("step_document_library.library_form").id, view_type="form")
    assert etree.fromstring(form["arch"].encode()).xpath("//button[@name='action_copy_external_url']")
    folder = doc.folder_id
    assert folder and folder.type == "folder"
    action = folder.action_open()
    assert doc.id in scope["documents.document"].search(action["domain"]).ids
    internal = doc.action_open()
    assert internal["url"] == "/web/content/%d?download=true" % attachment.id
    payload = attachment.raw
    length, sha = len(payload), hashlib.sha256(payload).hexdigest()
    assert payload.startswith(b"%PDF-") and length == attachment.file_size and hashlib.sha1(payload).hexdigest() == attachment.checksum
    external = doc.action_copy_external_url()
    wizard = scope[external["res_model"]].with_context(**external["context"])
    values = wizard.onchange({}, [], {"document_id": {"fields": {"display_name": {}}}, "url": {}})["value"]
    reference = doc._original_external_reference()
    assert values["document_id"]["id"] == doc.id and urlsplit(values["url"]).path == "/odoo/documents/" + quote(reference, safe="")
    public = env(user=env.ref("base.public_user").id, su=False)
    try:
        public["ir.attachment"].browse(attachment.id).check("read")
    except AccessError:
        pass
    else:
        raise AssertionError("Private payroll document accessible without a user")
    actors = [(env["res.users"].browse(uid), login, password) for uid, login, password in prepared]
    assert len(actors) == 2 and all(account.share and account.has_group("base.group_portal") and account.login == login
                                    and login.startswith("community-portal-") for account, login, _ in actors)
    # Opening a specific payslip uses its company. The ordinary recipient selector also
    # needs the portal accounts' company enabled for this same multi-company manager.
    eligible_companies = sorted(set([slip.company_id.id, *(a.company_id.id for a, _, _ in actors)]))
    assert set(eligible_companies) <= set(manager.company_ids.filtered('active').ids)
    grant_doc = doc.with_context(allowed_company_ids=eligible_companies)
    assert not grant_doc.env.su and grant_doc.may_manage_access
    grant_doc.env['res.users'].browse([a.id for a, _, _ in actors]).check_access('read')
    env.registry.enter_test_mode(env.cr)
    try:
        clients = {"recipient": session(env.cr.dbname, actors[0]), "other": session(env.cr.dbname, actors[1]),
                   "anonymous": session(env.cr.dbname)}
        content = "/documents/content/" + quote(reference, safe="")
        results = {}
        def compare(state, allowed):
            env.flush_all()
            env.invalidate_all()
            results[state] = {}
            for role, client in clients.items():
                result = client.get(content, base_url="http://localhost", environ_overrides={"REMOTE_ADDR": "127.0.0.1"})
                ok = role in allowed
                assert result.status_code == (200 if ok else 404), (state, role, result.status_code)
                if ok:
                    assert result.mimetype == "application/pdf" and len(result.data) == length
                    assert hashlib.sha256(result.data).hexdigest() == sha
                    assert "no-store" in result.headers["Cache-Control"]
                else:
                    assert not result.data.startswith(b"%PDF-")
                results[state][role] = result.status_code
        compare("restricted", set())
        individual(grant_doc, actors[0][0], "view", False)
        compare("recipient_granted", {"recipient"})
        individual(grant_doc, actors[0][0], "none", False)
        compare("recipient_revoked", set())
        return {"manager": manager.id, "same_pdf_sha256": sha, "bytes": length, "linked_private_pdfs": eligible,
                "payroll_form": True, "library_menu_folder_form": True, "original_editor_link": True,
                "ordinary_payroll_and_attachment": True, "excluded_company_denied": True, "public_attachment_denied": True,
                "selected_recipient_companies": eligible_companies, "document": doc.id, "attachment": attachment.id, "payslip": slip.id, "http": results}
    finally:
        env.registry.leave_test_mode()
        env.cr.rollback()
