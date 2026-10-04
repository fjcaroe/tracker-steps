from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..lib.step_app_core import tokens

INVITATION_DAYS = 7


class StepAppInvitation(models.Model):
    _name = "step.app.invitation"
    _description = "Invitación a una empresa"
    _order = "create_date desc"

    company_id = fields.Many2one("res.company", required=True, index=True, default=lambda self: self.env.company)
    email = fields.Char(required=True, index=True)
    state = fields.Selection(
        [("pending", "Pendiente"), ("accepted", "Aceptada"), ("cancelled", "Cancelada"), ("expired", "Vencida")],
        default="pending", required=True, index=True)
    token_hash = fields.Char(copy=False, groups="base.group_system")
    expires_at = fields.Datetime(copy=False, index=True)
    membership_id = fields.Many2one("step.app.membership", copy=False, readonly=True)
    line_ids = fields.One2many("step.app.invitation.line", "invitation_id", string="Accesos que otorga")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals["email"] = (vals.get("email") or "").strip().lower()
        return super().create(vals_list)

    @api.model
    def _cron_expire(self):
        """Marca como vencidas las invitaciones pendientes cuyo plazo pasó y deja de aceptar su código."""
        late = self.sudo().search([("state", "=", "pending"), ("expires_at", "!=", False), ("expires_at", "<", fields.Datetime.now())])
        late.write({"state": "expired", "token_hash": False})
        return len(late)

    def issue_token(self):
        """Genera el código de la invitación. El valor en claro se devuelve una sola vez; solo se guarda su huella."""
        self.ensure_one()
        if self.state != "pending":
            raise UserError(_("Solo una invitación pendiente puede emitir código."))
        token = tokens.new_token(24)
        self.sudo().write({"token_hash": tokens.hash_token(token),
                           "expires_at": fields.Datetime.now() + timedelta(days=INVITATION_DAYS)})
        self.env["step.app.audit"].log("invitation_issued", company=self.company_id, detail=self.email)
        return token

    def action_issue_token(self):
        self.ensure_one()
        token = self.issue_token()
        return {
            "type": "ir.actions.client", "tag": "display_notification",
            "params": {"title": _("Código de invitación"), "sticky": True, "type": "success",
                       "message": _("Entréguelo a %(email)s por un canal seguro. No volverá a mostrarse: %(token)s",
                                    email=self.email, token=token)},
        }

    def action_cancel(self):
        self.write({"state": "cancelled", "token_hash": False})


class StepAppInvitationLine(models.Model):
    _name = "step.app.invitation.line"
    _description = "Acceso otorgado por una invitación"

    invitation_id = fields.Many2one("step.app.invitation", required=True, ondelete="cascade")
    role_id = fields.Many2one("step.app.module.role", required=True)
    valid_to = fields.Datetime()
