from odoo import fields, models


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

    _sql_constraints = [("provider_subject_unique", "unique(provider, subject)", "Esta identidad ya está registrada.")]
