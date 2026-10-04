from odoo import fields, models


class StepAppDevice(models.Model):
    _name = "step.app.device"
    _description = "Dispositivo de una persona"
    _order = "last_seen_at desc"

    person_id = fields.Many2one("step.app.person", required=True, ondelete="cascade", index=True)
    uuid = fields.Char(required=True, index=True)
    kind = fields.Selection([("personal", "Personal"), ("shared", "Compartido")], default="personal", required=True)
    platform = fields.Char()
    label = fields.Char()
    app_version = fields.Char()
    last_seen_at = fields.Datetime()
    revoked_at = fields.Datetime(readonly=True)

    _sql_constraints = [("person_uuid_unique", "unique(person_id, uuid)", "Dispositivo duplicado para esta persona.")]

    def action_revoke(self):
        now = fields.Datetime.now()
        for device in self:
            device.write({"revoked_at": now})
            sessions = self.env["step.app.session"].sudo().search([("device_id", "=", device.id), ("revoked_at", "=", False)])
            sessions.write({"revoked_at": now, "revoked_reason": "device_revoked"})
            self.env["step.app.audit"].log("device_revoked", person=device.person_id, detail=device.label or device.uuid)
