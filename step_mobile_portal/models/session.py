from odoo import fields, models


class StepAppSession(models.Model):
    _name = "step.app.session"
    _description = "Sesión revocable"
    _order = "create_date desc"

    person_id = fields.Many2one("step.app.person", required=True, ondelete="cascade", index=True)
    device_id = fields.Many2one("step.app.device", required=True, ondelete="cascade", index=True)
    access_hash = fields.Char(required=True, index=True, groups="base.group_system")
    access_expires_at = fields.Datetime(required=True)
    refresh_hash = fields.Char(required=True, index=True, groups="base.group_system")
    previous_refresh_hash = fields.Char(index=True, groups="base.group_system")
    refresh_expires_at = fields.Datetime(required=True)
    last_used_at = fields.Datetime()
    validated_at = fields.Datetime(help="Última vez que el servidor confirmó los permisos (base del plazo sin conexión).")
    revoked_at = fields.Datetime(index=True)
    revoked_reason = fields.Char()
