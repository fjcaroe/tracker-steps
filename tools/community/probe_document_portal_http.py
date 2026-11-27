"""Check native and Community portal file sharing using temporary, genuinely authenticated accounts."""
import hashlib
import json
from pathlib import Path
import secrets
from urllib.parse import urlsplit
import uuid

from werkzeug.test import Client
from werkzeug.wrappers import Response

from odoo import http


PAYLOAD = b"Community portal fixture. No historical records.\n"
NAME = "community-portal-test.txt"
NATIVE = "MANAGEMENT_QA_SYS_PORTAL_20261126U41P"
COMMUNITY = "COMMUNITY_PORTAL_SYS_20261126U41P"
PREPARED = "COMMUNITY_PORTAL_SYS_20261126U41PA"
FOLDERS = "COMMUNITY_PORTAL_SYS_20261126U41PF"
COMBINED = "COMMUNITY_SYS_PREVIRED_COHORT_20261127U43C"


def new_portal(env, owner):
    group = env.ref("base.group_portal")
    login = "community-portal-" + uuid.uuid4().hex
    password = secrets.token_urlsafe(28)
    account = env["res.users"].create({
        "name": "Cuenta temporal del ensayo", "login": login, "password": password,
        "email": False, "groups_id": [(6, 0, [group.id])], "company_id": owner.company_id.id,
        "company_ids": [(6, 0, [owner.company_id.id])],
    })
    return account, login, password


def session(db, account=None):
    client = Client(http.root, Response, use_cookies=True)
    if account:
        user, login, password = account
        response = client.post("/web/session/authenticate", base_url="http://localhost",
                               environ_overrides={"REMOTE_ADDR": "127.0.0.1"},
                               json={"jsonrpc": "2.0", "method": "call", "id": 1,
                                     "params": {"db": db, "login": login, "password": password}})
        assert response.status_code == 200 and response.get_json()["result"]["uid"] == user.id
    return client


def observation(client, reference):
    section = {}
    paths = {"document": "/documents/" + reference, "content": "/documents/content/" + reference,
             "legacy": "/documents/redirect/" + reference, "bookmark": "/odoo/documents/" + reference}
    for label, path in paths.items():
        response = client.get(path, base_url="http://localhost", environ_overrides={"REMOTE_ADDR": "127.0.0.1"},
                              follow_redirects=False)
        assert response.status_code < 500
        location = urlsplit(response.headers.get("Location", ""))
        destination = next((name for name, candidate in paths.items() if location.path == candidate), None)
        section[label] = {
            "redirect_destination": destination, "redirect_has_query": bool(location.query),
            "status": response.status_code, "mime": response.mimetype, "fixture_bytes": response.data == PAYLOAD,
            "fixture_name_in_html": response.mimetype == "text/html" and NAME.encode() in response.data,
            "login_redirect": urlsplit(response.headers.get("Location", "")).path.startswith("/web/login"),
        }
    return section


def make_document(env, owner, native_fixture):
    attachment = env["ir.attachment"].create({"name": NAME, "raw": PAYLOAD, "mimetype": "text/plain", "public": False})
    if native_fixture is None:
        doc = env["documents.document"].create({
            "name": NAME, "type": "binary", "attachment_id": attachment.id, "owner_id": owner.id,
            "access_internal": "none", "access_via_link": "none",
        })
        return doc, {"id": doc.id, "reference": doc.access_token}
    ident, reference = native_fixture["id"], native_fixture["reference"]
    assert 0 < ident < 2**31 and 1 <= len(reference) <= 256
    alias = env["mail.alias"].create({"alias_model_id": env["ir.model"]._get_id("documents.document")})
    # Historical models are read-only in Community. Seed one synthetic row using its real table,
    # original domain and a fresh alias. No existing document, alias or token is modified.
    env.cr.execute("""
        INSERT INTO documents_document(id, name, type, attachment_id, owner_id, alias_id, active,
                  access_internal, access_via_link, document_token, step_portal_reference_hash,
                  create_uid, write_uid, create_date, write_date)
             VALUES(%s,%s,'binary',%s,%s,%s,true,'none','none',%s,%s,%s,%s,now(),now())
    """, [ident, NAME, attachment.id, owner.id, alias.id, secrets.token_urlsafe(16),
          hashlib.sha256(reference.encode()).hexdigest(), owner.id, owner.id])
    return env["documents.document"].browse(ident), native_fixture


def individual(document, target, level, native):
    env = document.env
    if native:
        access = env["documents.access"]
        rows = access.search([("document_id", "=", document.id), ("partner_id", "=", target.partner_id.id)])
        assert len(rows) <= 1
        if level != "none":
            if rows:
                rows.write({"role": level})
            else:
                access.create({"document_id": document.id, "partner_id": target.partner_id.id, "role": level})
        elif rows.last_access_date:
            rows.write({"role": False})
        elif rows:
            rows.unlink()
    else:
        action = document.action_manage_access()
        wizard = env[action["res_model"]].with_context(**action["context"]).create({
            "document_id": document.id, "user_id": target.id, "role": level,
        })
        wizard.action_apply()
    env.flush_all()


def sharing(document, level, native):
    if native:
        document.write({"access_via_link": level})
    else:
        action = document.action_external_link_permission()
        wizard = document.env[action["res_model"]].with_context(**action["context"]).create({
            "document_id": document.id, "level": level,
        })
        wizard.action_apply()
    document.env.flush_all()


def prepare_accounts(env):
    assert env.cr.dbname in (PREPARED, COMBINED) and env.su
    owner = env["res.users"].browse(6)
    setup = env(context={"tracking_disable": True, "mail_create_nolog": True, "mail_create_nosubscribe": True,
                         "mail_notrack": True, "no_reset_password": True})
    env.cr.execute("SELECT max(id) FROM res_users")
    cutoff = env.cr.fetchone()[0]
    actors = [new_portal(setup, owner) for _ in range(2)]
    assert all(account.id > cutoff and account.share and account.has_group("base.group_portal")
               for account, _, _ in actors)
    env.flush_all()
    return [(account.id, login, password) for account, login, password in actors]


def probe(env, native_fixture=None, prepared=None):
    native = native_fixture is None
    allowed_copies = (NATIVE,) if native else (PREPARED, FOLDERS) if prepared else (COMMUNITY,)
    assert env.cr.dbname in allowed_copies
    assert {line.split(":")[0].strip() for line in Path("/proc/net/dev").read_text().splitlines()[2:]} == {"lo"}
    assert env.registry.test_cr is None
    settings = {"tracking_disable": True, "mail_create_nolog": True, "mail_create_nosubscribe": True,
                "mail_notrack": True, "no_reset_password": True}
    owner = env["res.users"].browse(6)
    ordinary = env(user=owner.id, su=False, context=dict(settings, allowed_company_ids=[owner.company_id.id]))
    env.registry.enter_test_mode(env.cr)
    try:
        setup = env(context=settings)
        setup["ir.config_parameter"].set_param("ir_attachment.location", "db")
        if prepared:
            people = [(env["res.users"].browse(uid), login, password) for uid, login, password in prepared]
            assert len(people) == 2 and all(
                user.login == login and login.startswith("community-portal-") and user.active and user.share
                and user.has_group("base.group_portal") for user, login, _ in people)
        else:
            people = [new_portal(setup, owner) for _ in range(2)]
        doc, fixture = make_document(ordinary, owner, native_fixture)
        setup.flush_all()
        actors = {"anonymous": session(env.cr.dbname), "recipient": session(env.cr.dbname, people[0]),
                  "other": session(env.cr.dbname, people[1])}
        ref = fixture["reference"]

        def read_all():
            return {role: observation(client, ref) for role, client in actors.items()}

        invalid = "unissued-" + uuid.uuid4().hex
        result = {"unknown": {role: observation(client, invalid) for role, client in actors.items()},
                  "restricted": read_all()}
        individual(doc, people[0][0], "view", native)
        result["by_recipient"] = read_all()
        individual(doc, people[0][0], "none", native)
        result["after_revoke"] = read_all()
        sharing(doc, "view", native)
        result["by_link"] = read_all()
        sharing(doc, "none", native)
        result["link_revoked"] = read_all()
        for state, allowed in (("unknown", set()), ("restricted", set()), ("by_recipient", {"recipient"}),
                               ("after_revoke", set()), ("by_link", set(actors)), ("link_revoked", set())):
            for role in actors:
                status = result[state][role]["content"]
                assert status["status"] == (200 if role in allowed else 404)
                assert status["fixture_bytes"] == (role in allowed)
        return result, fixture
    finally:
        env.registry.leave_test_mode()
        env.cr.rollback()
