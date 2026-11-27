"""Compare the original operators' ticket conversations and the invited portal user's message attachments."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from odoo.addons.portal.controllers.mail import PortalChatter
from odoo.addons.website.tools import MockRequest
from odoo.exceptions import AccessError, MissingError
from odoo.tests.common import HttpCase
from odoo.http import request


MODEL = "helpdesk.ticket"
COPIES = {"MANAGEMENT_QA_STEPS_CRM_20261126U42C", "COMMUNITY_STEPS_CRM_SUPPORT_20261127U44H3",
          "COMMUNITY_STEPS_CRM_INTEGRATED_20261127U46A", "COMMUNITY_STEPS_CRM_FISCAL_20261127U45F",
          "COMMUNITY_STEPS_EXPENSE_20261127U50E"}


def fingerprint(values):
    return hashlib.sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@contextmanager
def request_for(scope, path):
    # The copy runs Odoo shell without a listening server. Only its fixture port is absent.
    with patch.object(HttpCase, "http_port", return_value=0), MockRequest(scope, path=path, context=scope.context):
        assert request.env.uid == scope.uid and not request.env.su
        yield


def content(scope, attachment_id, token=None):
    with request_for(scope, "/web/content"):
        record = scope["ir.binary"]._find_record(res_id=attachment_id, access_token=token, field="raw")
        data = record.with_context(bin_size=False).raw
        assert data and len(data) == record.file_size and hashlib.sha1(data).hexdigest() == record.checksum
        return [record.id, len(data), hashlib.sha256(data).hexdigest()]


def denied_attachment_record(scope, attachment_id):
    try:
        scope["ir.attachment"].browse(attachment_id).check("read")
    except (AccessError, MissingError):
        return True
    return False


def internal(scope, ticket_ids):
    tickets = scope[MODEL].search([], order="id")
    assert tickets.ids == ticket_ids and not scope.su and scope.user._is_internal()
    conversations = []
    files = {}
    for ticket in tickets:
        ticket.check_access("read")
        domain = [("model", "=", MODEL), ("res_id", "=", ticket.id), ("message_type", "!=", "user_notification")]
        messages = scope["mail.message"]._message_fetch(domain, limit=500)["messages"]
        assert len(messages) < 500
        values = [(m.id, str(m.body or ""), m.message_type, m.author_id.id, m.subtype_id.id,
                   sorted(m.attachment_ids.ids)) for m in messages]
        conversations.append([ticket.id, fingerprint(values), len(values)])
        for file in ticket._get_mail_thread_data_attachments().filtered("store_fname"):
            if file.id not in files:
                files[file.id] = content(scope, file.id)
    return {"threads": len(tickets), "messages": sum(n for _, _, n in conversations),
            "thread_values_sha256": fingerprint(conversations), "attachments": len(files),
            "attachment_bytes": sum(v[1] for v in files.values()), "attachment_values_sha256": fingerprint(sorted(files.values()))}


def portal(scope, public, invited_ids, outside):
    assert not scope.su and not scope.user._is_internal() and not scope.user._is_public()
    assert scope[MODEL].search([], order="id").ids == invited_ids
    route = PortalChatter()
    messages = []
    files = {}
    for ticket_id in invited_ids:
        with request_for(scope, "/mail/chatter_fetch"):
            result = route.portal_message_fetch(MODEL, ticket_id, limit=500)
        view = result["data"]["mail.message"]
        assert len(view) < 500
        for row in view:
            assert row["model"] == MODEL and row["res_id"] == ticket_id and not row.get("is_internal")
            linked = []
            for file in row["attachment_ids"]:
                # This is the link delivered by the portal for this message, scoped to the current transaction.
                assert file["access_token"]
                key = file["id"]
                files[key] = content(scope, key, file["access_token"])
                linked.append(key)
            messages.append([ticket_id, row["id"], str(row["body"] or ""), row["message_type"], sorted(linked)])
    assert files and messages, ("visible-attachments", len(files), len(messages))
    rejected = 0
    for actor, ticket_id in ((scope, outside), (public, invited_ids[0]), (public, outside)):
        # The ticket must be denied before its private conversation is requested.
        if not actor[MODEL].browse(ticket_id).has_access("read"):
            rejected += 1
    assert rejected == 3, ("scope-denials", rejected)
    raw_access = [denied_attachment_record(scope, key) for key in sorted(files)]
    public_access = [denied_attachment_record(public, key) for key in sorted(files)]
    assert all(public_access), ("ordinary-file-denials", sum(public_access), len(files))
    return {"invited_threads": len(invited_ids), "messages": len(messages), "attachments": len(files),
            "thread_values_sha256": fingerprint(messages), "attachment_values_sha256": fingerprint(sorted(files.values())),
            "attachment_bytes": sum(v[1] for v in files.values()), "unrelated_or_public_thread_denials": rejected,
            "portal_attachment_record_denials": sum(raw_access), "public_attachment_record_denials": sum(public_access)}


def run(env):
    assert __debug__ and env.cr.dbname in COPIES
    assert {line.split(":")[0].strip() for line in Path("/proc/net/dev").read_text().splitlines()[2:]} == {"lo"}
    env.cr.rollback()
    env.cr.execute("SELECT id FROM helpdesk_ticket ORDER BY id")
    tickets = [row[0] for row in env.cr.fetchall()]
    assert len(tickets) == 243
    env.cr.execute("""SELECT u.id, array_agg(DISTINCT f.res_id ORDER BY f.res_id)
                        FROM res_users u JOIN mail_followers f ON f.partner_id=u.partner_id
                       WHERE u.active AND u.share AND f.res_model=%s AND f.res_id=ANY(%s) GROUP BY u.id""", (MODEL, tickets))
    (external_id, invited), = env.cr.fetchall()
    assert len(invited) == 5
    def as_actor(user):
        assert user.active or user._is_public()
        return env(user=user.id, su=False, context={"allowed_company_ids": [user.company_id.id], "lang": user.lang or "en_US",
                                                    "bin_size": False, "tracking_disable": True, "mail_notify_force_send": False})
    try:
        operator_results = [internal(as_actor(env["res.users"].browse(uid)), tickets) for uid in (7, 10)]
        guest = portal(as_actor(env["res.users"].browse(external_id)), as_actor(env.ref("base.public_user")),
                       invited, next(key for key in tickets if key not in invited))
        assert all(item["threads"] == 243 and item["attachments"] for item in operator_results)
        return {"operators": operator_results, "portal": guest}
    finally:
        # Portal formatting may issue a fresh attachment link. Discard it with all session work.
        env.cr.rollback()
