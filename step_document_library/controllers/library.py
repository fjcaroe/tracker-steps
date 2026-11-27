from hashlib import sha256

from werkzeug.exceptions import NotFound
from odoo import http
from odoo.http import request


class HistoricalLibrary(http.Controller):
    @http.route("/odoo/documents/<string:reference>", type="http", auth="user", methods=["GET"], readonly=True)
    def original_link(self, reference):
        """Open an original bookmark using the current session's document permissions."""
        if len(reference) > 256 or not request.env.user.has_group("base.group_user"):
            raise NotFound()
        digest = sha256(("/odoo/documents/" + reference).encode()).hexdigest()
        request.env.cr.execute("SELECT id FROM documents_document WHERE step_original_url_hash=%s", [digest])
        result = request.env.cr.fetchone()
        if not result:
            raise NotFound()
        doc = request.env["documents.document"].browse(result[0])
        if not doc.has_access("read"):
            raise NotFound()
        action = request.env.ref("step_document_library.action_library")
        return request.redirect(f"/odoo/action-{action.id}/{doc.id}")
