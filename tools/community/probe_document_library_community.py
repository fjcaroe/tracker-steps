"""Compare access with a private native role matrix and exercise the original library in isolation."""
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from lxml import etree
from werkzeug.test import EnvironBuilder
from werkzeug.exceptions import NotFound
from odoo import http
from odoo.addons.web.controllers.binary import Binary
from odoo.addons.step_document_library.controllers.library import HistoricalLibrary
from odoo.exceptions import AccessError


def check_matrix(env, baseline):
    combinations = comparisons = 0
    for user_id, user in baseline["users"].items():
        for label, expected in user["cases"].items():
            companies = [int(i) for i in label.split(",") if i]
            scope = env(user=int(user_id), su=False, context={"allowed_company_ids": companies, "active_test": False})
            documents = scope["documents.document"]
            try:
                rows = documents.search([]).read(["user_permission"], load=None)
            except AccessError:
                assert not expected["model_acl"]
                rows = []
            else:
                assert expected["model_acl"]
            for role in ("view", "edit", "none"):
                actual = {r["id"] for r in rows if r["user_permission"] == role}
                wanted = set(expected.get(role, []))
                assert actual == wanted, (role, len(actual - wanted), len(wanted - actual))
            combinations += 1
            comparisons += len(baseline["documents"])
    return combinations, comparisons


def open_text(scope, doc):
    action = doc.action_open()
    attachment = doc.attachment_id
    assert action["url"] == f"/web/content/{attachment.id}?download=true"
    assert attachment.mimetype == "text/plain"
    builder = EnvironBuilder(path=urlsplit(action["url"]).path, query_string={"download": "true"})
    try:
        request = http.Request(http.HTTPRequest(builder.get_environ()))
        request.db, request.env, request.params = scope.cr.dbname, scope, {"download": "true"}
        http._request_stack.push(request)
        try:
            response = Binary().content_common(id=attachment.id, download="true")
            try:
                assert response.status_code == 200
                response.direct_passthrough = False
                raw = response.get_data()
                assert len(raw) == attachment.file_size and hashlib.sha1(raw).hexdigest() == attachment.checksum
                return hashlib.sha256(raw).hexdigest()
            finally:
                if hasattr(response, "close"):
                    response.close()
        finally:
            http._request_stack.pop()
    finally:
        builder.close()


def check_original_bookmark(scope, document, url, allowed):
    path = urlsplit(url).path
    builder = EnvironBuilder(path=path)
    try:
        request = http.Request(http.HTTPRequest(builder.get_environ()))
        request.db, request.env, request.params = scope.cr.dbname, scope, {}
        http._request_stack.push(request)
        try:
            matcher = scope["ir.http"].routing_map().bind("localhost")
            rule, parameters = matcher.match(path, method="GET", return_rule=True)
            assert rule.endpoint.routing["auth"] == "user" and "reference" in parameters
            try:
                response = HistoricalLibrary().original_link(parameters["reference"])
            except NotFound:
                assert not allowed
            else:
                assert allowed
                action = scope.ref("step_document_library.action_library")
                assert urlsplit(response.location).path == f"/odoo/action-{action.id}/{document.id}"
        finally:
            http._request_stack.pop()
    finally:
        builder.close()


def probe(env, baseline, original_bookmarks):

    assert re.fullmatch(r"COMMUNITY_LIBRARY_(CERRO|SYS)_[A-Z0-9_]+", env.cr.dbname)
    assert {row.split(":")[0].strip() for row in Path("/proc/net/dev").read_text().splitlines()[2:]} == {"lo"}
    assert not env["ir.module.module"].search_count([("state", "=", "installed"), ("license", "=", "OEEL-1")])
    combinations, comparisons = check_matrix(env, baseline)
    originals = env["res.users"].browse([int(uid) for uid, val in baseline["users"].items() if val["internal"]])
    # Use one pre-existing text file with restricted internal access. No signature or payroll PDF is opened.
    env.cr.execute("""
        SELECT d.id FROM documents_document d JOIN ir_attachment a ON a.id=d.attachment_id
        JOIN documents_document parent ON parent.id=d.folder_id AND parent.type='folder'
        WHERE d.type='binary' AND d.access_internal='none' AND a.mimetype='text/plain' ORDER BY d.id
    """)
    candidates = [row[0] for row in env.cr.fetchall()]
    menu_id = "step_document_library.library_root"
    for user in originals:
        scope = env(user=user.id, su=False, context={"allowed_company_ids": user.company_ids.filtered("active").ids})
        library = scope["documents.document"]
        docs = library.search([("id", "in", candidates)], order="id")
        document = next((d for d in docs if d.may_manage_access and d.folder_id.has_access("read")), None)
        if not document:
            continue
        for reader in originals - user:
            read_scope = env(user=reader.id, su=False, context={"allowed_company_ids": reader.company_ids.filtered("active").ids})
            read_document = read_scope["documents.document"].browse(document.id)
            if document.company_id and document.company_id.id not in read_scope.companies.ids:
                continue
            if not read_document.has_access("read"):
                break
        else:
            continue
        break
    else:
        raise AssertionError("no original editor, restricted text file and previously excluded internal reader")
    assert not scope.su and not read_scope.su
    assert scope.ref(menu_id).id in scope["ir.ui.menu"]._visible_menu_ids()
    form = library.get_view(view_id=scope.ref("step_document_library.library_form").id, view_type="form")
    assert etree.fromstring(form["arch"].encode()).xpath("//button[@name='action_manage_access']")
    folder = document.folder_id
    assert document in library.search(folder.action_open()["domain"])
    bookmark = original_bookmarks[str(document.id)]
    check_original_bookmark(scope, document, bookmark, True)
    check_original_bookmark(read_scope, document, bookmark, False)
    content = open_text(scope, document)
    public = scope.ref("base.public_user")
    assert not document.with_user(public).has_access("read")
    action = document.action_manage_access()
    wizard = scope[action["res_model"]].with_context(**action["context"])
    assert wizard.get_view(view_id=scope.ref("step_document_library.permission_form").id, view_type="form")
    def apply(role):
        wizard.create({"document_id": document.id, "partner_id": reader.partner_id.id, "role": role}).action_apply()
    def grant_id():
        return scope["documents.access"].search([("document_id", "=", document.id),
                                                ("partner_id", "=", reader.partner_id.id)]).id
    original_grant = grant_id()
    apply("view")
    assert read_document.has_access("read") and read_document.user_permission == "view"
    assert open_text(read_scope, read_document) == content
    check_original_bookmark(read_scope, read_document, bookmark, True)
    try:
        read_document.action_manage_access()
    except AccessError:
        pass
    else:
        raise AssertionError("viewer could manage individual grants")
    added = grant_id()
    assert added and (not original_grant or original_grant == added)
    apply("view")
    assert grant_id() == added
    apply("none")
    assert grant_id() == added and not read_document.has_access("read")
    check_original_bookmark(read_scope, read_document, bookmark, False)
    urls = library.search([("type", "=", "url")])
    assert urls and all(link.action_open()["url"] == link.url for link in urls)
    env.cr.rollback()
    assert check_matrix(env, baseline) == (combinations, comparisons)
    print("LIBRARY_COMMUNITY=" + json.dumps({
        "users": len(originals), "company_contexts": combinations, "permissions_compared": comparisons,
        "documents": len(baseline["documents"]), "menu_folder_form_download": True,
        "same_text_sha256": content, "grant_replay_revoke": True, "public_denied": True,
        "original_url_actions": len(urls), "authenticated_original_bookmark": True, "rollback_matrix_repeated": True,
    }))
