from odoo import fields, models


class HelpdeskPortalSeen(models.Model):
    _name = "step.helpdesk.portal.seen"
    _description = "Última lectura de un ticket en el portal"

    user_id = fields.Many2one("res.users", required=True, ondelete="cascade", index=True)
    ticket_id = fields.Many2one("helpdesk.ticket", required=True, ondelete="cascade", index=True)
    last_seen_message_id = fields.Many2one("mail.message", ondelete="set null")
    last_seen_at = fields.Datetime(required=True, default=fields.Datetime.now)

    _sql_constraints = [
        ("user_ticket_unique", "unique(user_id, ticket_id)", "Solo puede existir una lectura por usuario y ticket."),
    ]
