"""Exercise historical folder policies over ordinary anonymous and authenticated portal HTTP sessions."""
from hashlib import sha256
from pathlib import Path
from urllib.parse import quote, urlsplit
from uuid import uuid4

from lxml import html

from audit_document_portal_folders import native_folder_children, native_request
from probe_document_portal_http import NATIVE, individual, new_portal, session


FOLDER_DB = "COMMUNITY_PORTAL_SYS_20261126U41PF"
SPECS = (
    ("parent", "folder", None, "none", False),
    ("listed", "binary", "parent", "view", False),
    ("hidden", "binary", "parent", "view", True),
    ("private", "binary", "parent", "none", False),
    ("personal", "binary", "parent", "none", False),
    ("nested", "folder", "parent", "view", False),
    ("leaf", "binary", "nested", "view", False),
)


def make_tree(env, owner, standard=None):
    native = standard is None
    fixture = {"label": uuid4().hex, "documents": {}, "policies": {}} if native else standard
    docs = {}
    for label, kind, parent, level, hidden in SPECS:
        name = "community-dir-" + fixture["label"] + "-" + label
        attachment = None
        if kind == "binary":
            attachment = env["ir.attachment"].create({"name": name, "raw": name.encode(), "public": False,
                                                     "mimetype": "text/plain"})
        parent_id = docs[parent].id if parent else None
        if native:
            vals = {"name": name, "type": kind, "owner_id": owner.id, "folder_id": parent_id,
                    "access_via_link": level, "is_access_via_link_hidden": hidden, "access_internal": "none"}
            if attachment:
                vals["attachment_id"] = attachment.id
            doc = env["documents.document"].create(vals)
            fixture["documents"][label] = (doc.id, doc.document_token, doc.access_token)
        else:
            ident, stored, reference = fixture["documents"][label]
            assert reference.count(stored) == 1 and len(stored) >= 16
            prefix, suffix = reference.split(stored)
            alias = env["mail.alias"].create({"alias_model_id": env["ir.model"]._get_id("documents.document")})
            env.cr.execute("""
                INSERT INTO documents_document
                  (id,name,type,attachment_id,owner_id,alias_id,folder_id,active,access_internal,access_via_link,
                   is_access_via_link_hidden,document_token,step_portal_reference_prefix,step_portal_reference_suffix,
                   step_portal_reference_hash,create_uid,write_uid,create_date,write_date)
                VALUES (%s,%s,%s,%s,%s,%s,%s,true,'none',%s,%s,%s,%s,%s,%s,%s,%s,now(),now())
            """, [ident, name, kind, attachment.id if attachment else None, owner.id, alias.id, parent_id, level,
                  hidden, stored, prefix, suffix, sha256(reference.encode()).hexdigest(), owner.id, owner.id])
            doc = env["documents.document"].browse(ident)
        docs[label] = doc
    env.flush_all()
    return docs, fixture


def copy_policy(env, docs, users, baseline=None):
    """Apply only the original configuration of these disposable documents before each screen opens."""
    observed = {}
    for key, doc in docs.items():
        if baseline is not None:
            policy = baseline[key]
            env.cr.execute("UPDATE documents_document SET access_via_link=%s,is_access_via_link_hidden=%s "
                           "WHERE id=%s", [policy["link"], policy["hidden"], doc.id])
            for role, user in users.items():
                env.cr.execute("DELETE FROM documents_access WHERE document_id=%s AND partner_id=%s",
                               [doc.id, user.partner_id.id])
                grant = policy["recipients"][role]
                if grant:
                    env.cr.execute("""
                        INSERT INTO documents_access(document_id,partner_id,role,last_access_date)
                        VALUES (%s,%s,%s,CASE WHEN %s THEN timezone('UTC',now()) ELSE NULL END)
                    """, [doc.id, user.partner_id.id, grant[0], grant[1]])
            env.invalidate_all()
        env.cr.execute("SELECT access_via_link,is_access_via_link_hidden FROM documents_document WHERE id=%s", [doc.id])
        level, hidden = env.cr.fetchone()
        people = {}
        for role, user in users.items():
            env.cr.execute("SELECT role,last_access_date IS NOT NULL,expiration_date FROM documents_access "
                           "WHERE document_id=%s AND partner_id=%s", [doc.id, user.partner_id.id])
            rows = env.cr.fetchall()
            assert len(rows) <= 1 and (not rows or not rows[0][2])
            people[role] = list(rows[0][:2]) if rows else None
        observed[key] = {"link": level, "hidden": hidden, "recipients": people}
    return observed


def examine(client, user, role, docs, fixture, native):
    result = {}
    refs = {k: row[2] for k, row in fixture["documents"].items()}
    def get(path):
        answer = client.get(path, base_url="http://localhost", environ_overrides={"REMOTE_ADDR": "127.0.0.1"},
                            follow_redirects=False)
        assert answer.status_code < 500
        return answer

    for focus in ("parent", "nested"):
        folder = docs[focus]
        folder.env.invalidate_all()
        response = get("/documents/" + quote(refs[focus], safe=""))
        tree = html.fromstring(response.data)
        if native:
            # A request gets a fresh record cache after a previous connection commits its change.
            folder.env.invalidate_all()
            ids = native_request(folder.env, user, lambda: native_folder_children(folder))
            entries = sorted(key for key, doc in docs.items() if ids is not None and doc.id in ids)
            allowed = ids is not None
            if role == "anonymous" and allowed:
                for entry in entries:
                    assert docs[entry].name.encode() in response.data
        else:
            titles = tree.xpath("//main/h1/text()")
            allowed = titles == [folder.name]
            entries = []
            links = tree.xpath("//main/ul/li/a")
            for link in links:
                matched = [key for key, doc in docs.items() if doc.name == link.text_content()]
                assert len(matched) == 1
                key = matched[0]
                assert urlsplit(link.get("href")).path == "/documents/" + quote(refs[key], safe="")
                assert not urlsplit(link.get("href")).query
                entries.append(key)
            assert len(entries) == len(set(entries))
            entries.sort()
            for key, doc in docs.items():
                if key != focus and key not in entries:
                    assert doc.name.encode() not in response.data and refs[key].encode() not in response.data
            if not allowed:
                assert not entries and folder.name.encode() not in response.data
        downloads = []
        for key in entries:
            child = docs[key]
            if child.type == "binary":
                downloaded = get("/documents/content/" + quote(refs[key], safe=""))
                assert downloaded.status_code == 200 and downloaded.data == child.name.encode()
                downloads.append(key)
        result[focus] = {"http": response.status_code, "allowed": allowed, "entries": entries, "downloads": downloads}
    return result


def folder_http(env, fixture=None, prepared=None):
    native = fixture is None
    assert env.cr.dbname == (NATIVE if native else FOLDER_DB)
    assert {line.split(":")[0].strip() for line in Path("/proc/net/dev").read_text().splitlines()[2:]} == {"lo"}
    assert env.registry.test_cr is None and native == (prepared is None)
    options = {"tracking_disable": True, "mail_create_nolog": True, "mail_create_nosubscribe": True,
               "no_reset_password": True, "mail_notrack": True}
    owner = env["res.users"].browse(6)
    ordinary = env(user=owner.id, su=False, context=dict(options, allowed_company_ids=[owner.company_id.id]))
    env.registry.enter_test_mode(env.cr)
    try:
        setup = env(context=options)
        setup["ir.config_parameter"].set_param("ir_attachment.location", "db")
        if native:
            accounts = [new_portal(setup, owner) for _ in range(2)]
        else:
            accounts = [(env["res.users"].browse(uid), login, pwd) for uid, login, pwd in prepared]
            assert len(accounts) == 2 and all(user.share and user.active and user.login == login
                                             and user.has_group("base.group_portal") for user, login, _ in accounts)
        docs, fixture = make_tree(ordinary, owner, fixture)
        users = {"anonymous": env.ref("base.public_user"), "recipient": accounts[0][0], "other": accounts[1][0]}
        clients = {"anonymous": session(env.cr.dbname), "recipient": session(env.cr.dbname, accounts[0]),
                   "other": session(env.cr.dbname, accounts[1])}
        if native:
            individual(docs["personal"], users["recipient"], "view", True)
        results = {}
        for label in ("restricted", "recipient", "recipient_revoked", "child_revoked", "child_restored",
                      "by_link", "link_revoked"):
            if native:
                if label in ("recipient", "recipient_revoked"):
                    individual(docs["parent"], users["recipient"], "view" if label == "recipient" else "none", True)
                elif label in ("child_revoked", "child_restored"):
                    individual(docs["personal"], users["recipient"], "view" if label == "child_restored" else "none", True)
                elif label in ("by_link", "link_revoked"):
                    docs["parent"].write({"access_via_link": "view" if label == "by_link" else "none"})
                env.invalidate_all()
                fixture["policies"][label] = copy_policy(env, docs, users)
            else:
                assert copy_policy(env, docs, users, fixture["policies"][label]) == fixture["policies"][label]
            results[label] = {role: examine(clients[role], user, role, docs, fixture, native)
                              for role, user in users.items()}
        return results, fixture
    finally:
        env.registry.leave_test_mode()
        env.cr.rollback()
