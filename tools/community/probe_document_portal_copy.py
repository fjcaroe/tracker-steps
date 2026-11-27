"""Compare the editor's actual clipboard field with the authenticated native sharing address."""
from hashlib import sha256
from urllib.parse import urlsplit

from lxml import etree
from odoo.exceptions import AccessError


def editor(env):
    actor = env["res.users"].browse(6)
    return env(user=actor.id, su=False, context={"allowed_company_ids": actor.company_ids.filtered("active").ids})


def native_editor_addresses(env):
    assert env.cr.dbname == "MANAGEMENT_QA_SYS_PORTAL_20261126U41P"
    source = editor(env)["documents.document"]
    samples = []
    for kind in ("binary", "folder"):
        for link_role in ("none", "view"):
            candidates = source.search([("type", "=", kind), ("access_via_link", "=", link_role),
                                        ("user_permission", "=", "edit")], order="id", limit=1)
            assert candidates
            url = candidates.get_base_url().rstrip("/") + candidates.access_url
            assert urlsplit(url).scheme in ("http", "https") and urlsplit(url).netloc
            samples.append([candidates.id, kind, link_role, sha256(url.encode()).hexdigest()])
    return samples


def community_editor_addresses(env, samples):
    assert env.cr.dbname == "COMMUNITY_PORTAL_SYS_20261126U41PF"
    scope = editor(env)
    model = scope["documents.document"]
    form = model.get_view(view_id=scope.ref("step_document_library.library_form").id, view_type="form")
    assert etree.fromstring(form["arch"].encode()).xpath("//button[@name='action_copy_external_url']")
    wizard_model = scope["step.document.library.reference"]
    view = wizard_model.get_view(view_id=scope.ref("step_document_library_portal.reference_form").id, view_type="form")
    assert etree.fromstring(view["arch"].encode()).xpath("//field[@name='url'][@widget='CopyClipboardChar']")
    denied = 0
    portal = env["res.users"].search([("active", "=", True), ("share", "=", True),
                                      ("login", "=like", "community-portal-%")])
    assert len(portal) == 2
    viewers = portal | env.ref("base.public_user")
    for row_id, kind, link_role, expected in samples:
        doc = model.browse(row_id)
        assert doc.type == kind and doc.access_via_link == link_role and doc.user_permission == "edit"
        action = doc.action_copy_external_url()
        assert action["res_model"] == wizard_model._name and action["target"] == "new"
        # Odoo opens a new form by requesting onchange with an empty list of changed fields.
        form_data = wizard_model.with_context(**action["context"]).onchange(
            {}, [], {"document_id": {"fields": {"display_name": {}}}, "url": {}},
        )["value"]
        assert form_data["document_id"]["id"] == row_id
        address = form_data["url"]
        assert sha256(address.encode()).hexdigest() == expected
        for actor in viewers:
            outsider = env(user=actor.id, su=False)["documents.document"].browse(row_id)
            try:
                outsider.action_copy_external_url()
            except AccessError:
                denied += 1
            else:
                raise AssertionError("The editor clipboard was available outside its allowed scope")
    env.cr.rollback()
    return {"copy_fields_verified": len(samples), "outside_editor_scope_denied": denied,
            "original_absolute_links_match": True, "widget": "CopyClipboardChar"}
