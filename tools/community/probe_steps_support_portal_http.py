"""Exercise the original Steps ticket URLs with genuinely signed-in synthetic portal users in a rolled-back copy."""
import hashlib
from pathlib import Path
import re
import uuid
from urllib.parse import urlencode, urlsplit

from lxml import html

from probe_document_portal_http import new_portal, session


MODEL = "helpdesk.ticket"
NATIVE = "MANAGEMENT_QA_STEPS_CRM_20261126U42C"
COMMUNITY = "COMMUNITY_STEPS_CRM_SUPPORT_20261127U44H3"
INTEGRATED = "COMMUNITY_STEPS_CRM_INTEGRATED_20261127U46A"
HOST = {"base_url": "http://localhost", "environ_overrides": {"REMOTE_ADDR": "127.0.0.1"}}


def get(client, url, **params):
    return client.get(url + (("?" + urlencode(params)) if params else ""), follow_redirects=False, **HOST)


def shown(client, path, ticket):
    response = get(client, path)
    if response.status_code in (301, 302, 303, 307, 308, 403, 404):
        return False
    assert response.status_code == 200, ("ticket-page", response.status_code)
    dom = html.fromstring(response.data)
    return bool(dom.xpath("//*[contains(concat(' ', normalize-space(@class), ' '), ' o_portal_chatter ')]")) and ticket.name in " ".join(dom.itertext())


def listed(client, **params):
    response = get(client, "/my/tickets", **params)
    assert response.status_code == 200, ("ticket-list", response.status_code)
    order = []
    for anchor in html.fromstring(response.data).xpath("//a[@href]"):
        match = re.fullmatch(r"(?:/[a-z]{2}(?:[-_][A-Za-z]{2})?)?/(?:my|helpdesk)/ticket/(\d+)(?:/[^/]*)?/?", urlsplit(anchor.get("href")).path)
        if match and int(match[1]) not in order:
            order.append(int(match[1]))
    return order


def view_messages(client, ticket_id):
    http_response = client.post("/mail/chatter_fetch", json={"jsonrpc": "2.0", "method": "call", "id": 1,
        "params": {"thread_model": MODEL, "thread_id": ticket_id, "limit": 500}}, **HOST)
    assert http_response.status_code == 200 and "result" in http_response.get_json()
    result = http_response.get_json()["result"]["data"]["mail.message"]
    assert len(result) < 500
    return result


def run(env):
    assert __debug__ and env.cr.dbname in (NATIVE, COMMUNITY, INTEGRATED, "COMMUNITY_STEPS_CRM_FISCAL_20261127U45F",
                                          "COMMUNITY_STEPS_EXPENSE_20261127U50E") and env.registry.test_cr is None
    assert {line.split(":")[0].strip() for line in Path("/proc/net/dev").read_text().splitlines()[2:]} == {"lo"}
    env.cr.rollback()
    options = {"tracking_disable": True, "mail_create_nolog": True, "mail_create_nosubscribe": True,
               "mail_notrack": True, "no_reset_password": True, "mail_notify_force_send": False}
    operator = env["res.users"].browse(7)
    ordinary = env(user=operator.id, su=False, context=dict(options, allowed_company_ids=[operator.company_id.id]))
    original = env["res.users"].browse(6)
    visible = env(user=original.id, su=False, context={"allowed_company_ids": [original.company_id.id]})[MODEL].search([], order="id")
    assert original.share and len(visible) == 5 and not ordinary.su
    tickets = ordinary[MODEL].browse(visible.ids)
    env.registry.enter_test_mode(env.cr)
    try:
        setup = env(context=options)
        setup["ir.config_parameter"].set_param("ir_attachment.location", "db")
        people = [new_portal(setup, operator) for _ in range(2)]
        # The native portal also filters tickets by the customer's commercial contact.
        people[0][0].partner_id.write({"parent_id": original.partner_id.commercial_partner_id.id})
        tickets.message_subscribe(partner_ids=[people[0][0].partner_id.id])
        setup.flush_all()
        recipient, other = [session(env.cr.dbname, person) for person in people]
        public = session(env.cr.dbname)
        granted = env(user=people[0][0].id, su=False, context={"allowed_company_ids": [operator.company_id.id]})[MODEL].search([], order="id")
        assert granted.ids == visible.ids, ("fixture-visibility", len(granted))
        ids = listed(recipient)
        assert len(ids) == 5 and set(ids) == set(tickets.ids) and not listed(other), ("ticket-lists", len(ids))
        sorts = {order: listed(recipient, sortby=order) for order in ("create_date asc", "create_date desc", "name", "id desc", "priority desc, write_date desc",
                                                                      "stage_id", "user_id", "write_date desc")}
        filters = {key: listed(recipient, filterby=key) for key in ("all", "open", "closed", "assigned", "unassigned")}
        assert set(sorts["name"]) == set(ids) and set(filters["open"]) | set(filters["closed"]) == set(ids)
        sample = tickets[0]
        groups = {key: listed(recipient, groupby=key) for key in ("none", "stage_id", "team_id", "user_id", "partner_id", "kanban_state")}
        search = {"name": listed(recipient, search_in="name", search=sample.name)}
        assert sample.id in search["name"] and all(set(order) == set(ids) for order in groups.values())
        form = html.fromstring(get(recipient, "/my/tickets").data)
        options = {"steps_priority", "steps_stage", "steps_status", "steps_assignment", "steps_period"}
        parameter_names = sorted({element.get("name") for element in form.xpath("//form//*[self::input or self::select][@name]")
                                  if element.get("name") in options})
        extra = {}
        for field in parameter_names:
            name = field.removeprefix("steps_")
            input_value = {"priority": sample.priority, "stage": str(sample.stage_id.id), "status": "open",
                           "assignment": "unassigned", "period": "7"}[name]
            extra[field] = listed(recipient, **{field: input_value})
        aliases = []
        for ticket in tickets:
            alias = "/helpdesk/ticket/%s" % ticket.id
            response = get(recipient, alias)
            location = urlsplit(response.headers.get("Location", "")).path
            canonical = re.fullmatch(r"(?:/[a-z]{2}(?:[-_][A-Za-z]{2})?)?/my/ticket/(\d+)/?", location)
            if response.status_code == 200:
                dom = html.fromstring(response.data)
                ready = ticket.name in " ".join(dom.itertext())
                aliases.append(["direct", ready])
            elif canonical and int(canonical[1]) == ticket.id and response.status_code in (301, 302, 303, 307, 308):
                aliases.append(["canonical-redirect", True])
            else:
                safe = [s if s in ("my", "ticket", "tickets", "helpdesk", "odoo", "web", "login", "es", "en") else "<part>"
                        for s in location.split("/") if s]
                raise AssertionError(("ticket-link", response.status_code, "/" + "/".join(safe)))
        assert all(case[1] for case in aliases), ("ticket-link", aliases)
        results = []
        attachments = {}
        for ticket in tickets:
            path = "/my/ticket/%s" % ticket.id
            assert shown(recipient, path, ticket) and not shown(other, path, ticket) and not shown(public, path, ticket)
            for message in view_messages(recipient, ticket.id):
                assert message["res_id"] == ticket.id and not message["is_internal"]
                linked = []
                for file in message["attachment_ids"]:
                    # Use the file link issued to this test user by the authorized conversation.
                    assert file["access_token"]
                    download = get(recipient, "/web/content/%s" % file["id"], access_token=file["access_token"], download="true")
                    assert download.status_code == 200 and hashlib.sha1(download.data).hexdigest() == file["checksum"]
                    attachments[file["id"]] = [len(download.data), hashlib.sha256(download.data).hexdigest()]
                    linked.append(file["id"])
                results.append([ticket.id, message["id"], sorted(linked)])
        assert len(results) == 3 and len(attachments) == 2
        # Issue and expire a link solely on a new fixture. No existing ticket token is consulted.
        fixture = ordinary[MODEL].create({"name": "Ensayo transitorio del portal", "team_id": tickets[0].team_id.id,
                                         "stage_id": tickets[0].stage_id.id})
        token = fixture._portal_ensure_token()
        ordinary.flush_all()
        path = "/my/ticket/%s/" % fixture.id
        assert token and shown(public, path + token, fixture) and not shown(public, path + uuid.uuid4().hex, fixture)
        fixture.write({"access_token": False})
        ordinary.flush_all()
        assert not shown(public, path + token, fixture)
        return {"authenticated_sessions": 2, "visible_order": ids, "sorts": sorts, "filters": filters, "groups": groups, "search": search,
                "extended_form_parameters": extra,
                "linked_ticket_pages": aliases, "recipient_details": len(ids), "other_details_denied": len(ids), "anonymous_details_denied": len(ids),
                "messages": results, "files": attachments, "temporary_link_accepted": True,
                "invalid_link_denied": True, "expired_link_denied": True}
    finally:
        env.registry.leave_test_mode()
        env.cr.rollback()
