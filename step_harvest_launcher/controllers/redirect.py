"""Canonical entry point for the Steps Harvest PWA.

Odoo can be reached directly on a VM port, while Nginx serves the PWA only on
the public HTTPS hostname. Redirect legacy direct-port URLs and the app menu
to the hostname configured for this database.
"""

from urllib.parse import urlsplit

from odoo import http
from odoo.http import request


class HarvestRedirect(http.Controller):
    @http.route(
        ['/harvest/open', '/cosecha', '/cosecha/'],
        type='http',
        auth='public',
        methods=['GET', 'HEAD'],
        sitemap=False,
    )
    def open_harvest(self, **kwargs):
        target = request.env['ir.config_parameter'].sudo().get_param('steps.harvest.url', '')
        parsed = urlsplit(target)
        valid_host = parsed.hostname == 'stepsapp.cl' or (
            parsed.hostname and parsed.hostname.endswith('.stepsapp.cl')
        )
        if not (parsed.scheme == 'https' and valid_host and parsed.path == '/cosecha/'
                and not parsed.username and not parsed.password and not parsed.query
                and not parsed.fragment):
            return request.not_found()
        response = request.redirect(target, code=302, local=False)
        response.headers['Cache-Control'] = 'no-store'
        return response
