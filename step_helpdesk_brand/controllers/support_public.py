"""Public entry points for the existing Helpdesk website form and portal."""

from odoo import http
from odoo.http import request


class StepsSupportPublic(http.Controller):
    @staticmethod
    def _published_form_team():
        teams = request.env["helpdesk.team"].sudo().search([
            ("use_website_helpdesk_form", "=", True),
            ("website_published", "=", True),
            ("privacy_visibility", "=", "portal"),
        ], order="sequence, id")
        return teams.filtered(
            lambda team: not team.website_id or team.website_id.id == request.website.id
        )[:1]

    @http.route("/soporte", type="http", auth="public", website=True, sitemap=False)
    def support_home(self, **kwargs):
        return request.render("step_helpdesk_brand.support_public_home", {
            "support_team": self._published_form_team(),
        })

    @http.route("/soporte/nueva-solicitud", type="http", auth="public", website=True, sitemap=False)
    def support_new_ticket(self, **kwargs):
        team = self._published_form_team()
        return request.redirect(team.website_url if team else "/soporte", code=302)
