"""Compare historical binary sharing decisions without opening any historical file."""
import hashlib
import logging
from pathlib import Path
from unittest.mock import patch

from werkzeug.exceptions import Forbidden, NotFound
from werkzeug.test import EnvironBuilder

from odoo import http


def binary_scope(env, native):
    expected = "MANAGEMENT_QA_SYS_PORTAL_20261126U41P" if native else "COMMUNITY_PORTAL_SYS_20261126U41P"
    assert env.cr.dbname == expected and {s.split(":")[0].strip() for s in
                                          Path("/proc/net/dev").read_text().splitlines()[2:]} == {"lo"}
    public = env.ref("base.public_user")
    scope = env(user=public.id, su=False, context={"allowed_company_ids": [public.company_id.id]})
    assert not scope.su and scope.user._is_public()
    env.cr.execute("SELECT id FROM documents_document WHERE type='binary' ORDER BY id")
    ids = [row[0] for row in env.cr.fetchall()]
    checked = {}
    if native:
        from odoo.addons.documents.controllers.documents import ShareRoute

        class MetadataStream:
            def __init__(self, original_id):
                self.original_id = original_id

            def get_response(self, *args, **kwargs):
                return http.Response(status=200, headers={"X-Test-Document-Id": str(self.original_id)})

        builder = EnvironBuilder(path="/documents/content/", environ_base={"REMOTE_ADDR": "127.0.0.1"})
        req = http.Request(http.HTTPRequest(builder.get_environ()))
        req.env, req.db, req.params = scope, env.cr.dbname, {}
        req.session = http.root.session_store.new()
        req.session.update(http.get_default_session(), db=env.cr.dbname)
        http._request_stack.push(req)
        previous = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        try:
            # Native routing, selection and access checks execute normally. Replace only the final
            # file stream, whose content is outside the scope of this historical permissions audit.
            with patch.object(ShareRoute, "_documents_content_stream",
                              lambda self, document_sudo: MetadataStream(document_sudo.id)):
                controller = ShareRoute()
                for row in env["documents.document"].with_context(active_test=False).browse(ids):
                    try:
                        response = controller.documents_content(row.access_token)
                    except (Forbidden, NotFound):
                        checked[row.id] = False
                    else:
                        assert response.status_code in (200, 403, 404)
                        checked[row.id] = response.status_code == 200
                        if checked[row.id]:
                            assert response.headers.get("X-Test-Document-Id") == str(row.id)
        finally:
            logging.disable(previous)
            http._request_stack.pop()
            builder.close()
            env.cr.rollback()
    else:
        env.cr.execute("SELECT id,step_portal_reference_hash FROM documents_document WHERE type='binary' ORDER BY id")
        for row, digest in env.cr.fetchall():
            assert digest
            record = scope["documents.document"]._external_file_by_digest(digest)
            checked[row] = bool(record)
            assert not record or record.id == row
        env.cr.rollback()
    assert set(checked) == set(ids)
    return {"decisions": checked, "public_uid": public.id, "count": len(ids),
            "allowed": sum(checked.values()), "result_hash": hashlib.sha256(
                ",".join(str(row) for row in ids if checked[row]).encode()).hexdigest()}
