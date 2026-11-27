from werkzeug.exceptions import NotFound

from odoo import http
from odoo.http import request


class SharedDocument(http.Controller):
    @http.route("/documents/content/<string:reference>", auth="public", type="http", methods=["GET"], readonly=True)
    def content(self, reference, download=None, **params):
        document = request.env["documents.document"]._external_file(reference)
        if not document:
            raise NotFound()
        stream = request.env["ir.binary"]._get_stream_from(document.attachment_id)
        response = stream.get_response(as_attachment=download in ("1", "true", "True"), immutable=False)
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @http.route("/documents/<string:reference>", auth="public", type="http", methods=["GET"], readonly=True)
    def document(self, reference, **params):
        document = request.env["documents.document"]._external_file(reference)
        if not document:
            raise NotFound()
        response = request.render("step_document_library_portal.shared_document", {
            "file_name": document.name, "reference": reference,
        })
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response
