from odoo import _, fields, models
from odoo.exceptions import UserError


class StepAppIdentity(models.Model):
    _name = "step.app.identity"
    _description = "Identidad externa de una persona"
    _order = "person_id, provider"

    person_id = fields.Many2one("step.app.person", required=True, ondelete="cascade", index=True)
    provider = fields.Selection(
        [("password", "Contraseña"), ("google", "Google"), ("apple", "Apple"), ("test", "Prueba")], required=True)
    subject = fields.Char(required=True, index=True, help="Identificador estable del proveedor (sub). Para contraseña, el correo normalizado.")
    email = fields.Char(index=True)
    email_verified = fields.Boolean(default=False)
    secret_hash = fields.Char(groups="base.group_system", copy=False)
    failed_attempts = fields.Integer(default=0)
    locked_until = fields.Datetime()
    verify_token_hash = fields.Char(groups="base.group_system", copy=False)
    verify_expires_at = fields.Datetime(copy=False)
    reset_token_hash = fields.Char(groups="base.group_system", copy=False)
    reset_expires_at = fields.Datetime(copy=False)

    def action_mark_email_verified(self):
        """Verificación manual por un administrador del sistema (cuando no hay correo saliente configurado). Queda auditada."""
        for identity in self:
            identity.write({"email_verified": True, "verify_token_hash": False, "verify_expires_at": False})
            self.env["step.app.audit"].log("email_verified_by_admin", person=identity.person_id, detail=identity.email or "")

    def action_issue_recovery_code(self):
        """Código de recuperación emitido por un administrador del sistema (p. ej. cuando el correo saliente no está configurado).
        Se muestra una sola vez; solo se guarda su huella. Quien lo use define una contraseña nueva y se cierran todas sus sesiones."""
        self.ensure_one()
        if self.provider != "password":
            raise UserError(_("Solo las cuentas con contraseña se recuperan con código."))
        token = self.env["step.app.api"]._issue_recovery(self)
        self.env["step.app.audit"].log("recovery_code_issued", person=self.person_id, detail="emitido por administrador")
        return {"type": "ir.actions.client", "tag": "display_notification",
                "params": {"title": _("Código de recuperación"), "sticky": True, "type": "success",
                           "message": _("Entréguelo a %(name)s por un canal seguro (vence en 2 horas): %(token)s", name=self.person_id.name, token=token)}}

    _sql_constraints = [("provider_subject_unique", "unique(provider, subject)", "Esta identidad ya está registrada.")]
