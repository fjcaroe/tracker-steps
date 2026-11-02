from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError
from odoo.addons.step_tracker_portal.controllers.portal import company
from odoo.addons.step_management_costs_tracker.controllers.costs import TrackerCostsController


class RestrictedCosts(TrackerCostsController):
    @http.route()
    def asset_costs(self, asset_id, **params):
        try:
            request.env.user._tracker_check_asset(company(), asset_id)
        except AccessError:
            return request.make_json_response({'detail': 'Activo no encontrado.'}, status=404,
                headers={'Cache-Control': 'no-store'})
        return super().asset_costs(asset_id, **params)
