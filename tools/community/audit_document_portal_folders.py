"""Compare original public folder decisions and listed child IDs without reading any attachment."""
import hashlib
import json
import logging
from pathlib import Path

from werkzeug.exceptions import Forbidden, NotFound
from werkzeug.test import EnvironBuilder

from odoo import http


def native_request(env, user, function):
    scope = env(user=user.id, su=False, context={"allowed_company_ids": [user.company_id.id]})
    builder = EnvironBuilder(path="/documents/", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    req = http.Request(http.HTTPRequest(builder.get_environ()))
    req.env, req.db, req.params = scope, env.cr.dbname, {}
    req.session = http.root.session_store.new()
    req.session.update(http.get_default_session(), db=env.cr.dbname)
    if not scope.user._is_public():
        req.session.uid = user.id
    http._request_stack.push(req)
    previous = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        return function()
    finally:
        logging.disable(previous)
        http._request_stack.pop()
        builder.close()


def native_folder_children(document):
    from odoo.addons.documents.controllers.documents import ShareRoute

    try:
        folder = ShareRoute._from_access_token(document.access_token)
    except (Forbidden, NotFound):
        return None
    if not folder:
        return None
    assert folder.id == document.id and folder.type == "folder"
    return sorted(ShareRoute._get_folder_children(folder).ids)


def folder_scope(env, native):
    assert env.cr.dbname == ("MANAGEMENT_QA_SYS_PORTAL_20261126U41P" if native else "COMMUNITY_PORTAL_SYS_20261126U41PF")
    assert {s.split(":")[0].strip() for s in Path("/proc/net/dev").read_text().splitlines()[2:]} == {"lo"}
    public = env.ref("base.public_user")
    env.cr.execute("SELECT id FROM documents_document WHERE type='folder' ORDER BY id")
    rows = [r[0] for r in env.cr.fetchall()]
    if native:
        records = env["documents.document"].with_context(active_test=False).browse(rows)
        tree = native_request(env, public, lambda: {doc.id: native_folder_children(doc) for doc in records})
    else:
        env.cr.execute("SELECT id,step_portal_reference_hash FROM documents_document WHERE type='folder' ORDER BY id")
        candidates = env.cr.fetchall()
        library = env(user=public.id, su=False)["documents.document"]
        tree = {}
        for row, digest in candidates:
            assert digest
            folder = library._external_item_by_digest(digest, ["folder"])
            tree[row] = sorted(library._listed_folder_children(folder).ids) if folder else None
    assert set(tree) == set(rows)
    env.cr.rollback()
    return {"folders": len(tree), "allowed": sum(children is not None for children in tree.values()),
            "visible_entries": sum(len(children) for children in tree.values() if children is not None),
            "tree_hash": hashlib.sha256(json.dumps(tree, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "tree": tree}
