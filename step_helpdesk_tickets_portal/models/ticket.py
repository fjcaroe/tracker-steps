from odoo import models


class Ticket(models.Model):
    _name = "helpdesk.ticket"
    _inherit = ["helpdesk.ticket", "portal.mixin"]

    def _compute_access_url(self):
        for ticket in self:
            ticket.access_url = "/my/ticket/%s" % ticket.id
