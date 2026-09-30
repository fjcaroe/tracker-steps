"""Redirect legacy Helpdesk entry URLs after the support hostname is live."""

import werkzeug.exceptions

from odoo import SUPERUSER_ID, models
from odoo.http import request


CANONICAL_HOST = "soporte.stepsapp.cl"
LEGACY_HOSTS = {"35.222.25.110", "stepsapp.cl", "www.stepsapp.cl"}
BACKEND_ROUTES = (
    "/odoo/helpdesk", "/odoo/all-tickets", "/odoo/my-tickets",
    "/odoo/tickets-analysis", "/odoo/sla-status-analysis",
    "/odoo/helpdesk-teams", "/odoo/sla-policies",
)
PORTAL_ROUTES = ("/my/tickets", "/my/ticket", "/helpdesk/ticket")


def is_helpdesk_path(path):
    return any(path == route or path.startswith(route + "/") for route in BACKEND_ROUTES) or any(
        path == route or path.startswith(route + "/") for route in PORTAL_ROUTES
    )


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _authenticate(cls, endpoint):
        # Authentication normally redirects anonymous users to /web/login.
        # Canonicalize the entry URL first so their login also uses HTTPS.
        http_request = request.httprequest
        if http_request.method in ("GET", "HEAD") and is_helpdesk_path(http_request.path):
            host = http_request.host.split(":", 1)[0].lower()
            if host in LEGACY_HOSTS and request.env["ir.config_parameter"].with_user(SUPERUSER_ID).get_param(
                "step_helpdesk_brand.canonical_enabled", "False"
            ) == "True":
                path_and_query = http_request.full_path.rstrip("?")
                werkzeug.exceptions.abort(cls._redirect(f"https://{CANONICAL_HOST}{path_and_query}", code=301))
        return super()._authenticate(endpoint)
