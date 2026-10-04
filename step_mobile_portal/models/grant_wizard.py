from odoo import _, fields, models
from odoo.exceptions import UserError


class StepAppGrantWizard(models.TransientModel):
    _name = "step.app.grant.wizard"
    _description = "Asignar módulos y roles a una membresía"

    membership_id = fields.Many2one("step.app.membership", required=True, readonly=True)
    person_id = fields.Many2one(related="membership_id.person_id")
    company_id = fields.Many2one(related="membership_id.company_id")
    role_ids = fields.Many2many("step.app.module.role", string="Módulos y roles", required=True)
    valid_from = fields.Datetime()
    valid_to = fields.Datetime(string="Vence")
    approve = fields.Boolean(string="Activar la membresía si está pendiente", default=True)

    def action_assign(self):
        """Asignación común en un paso: crea las concesiones que falten y, si se pide, activa la membresía. Todo queda auditado."""
        self.ensure_one()
        membership = self.membership_id
        if membership.state in ("revoked",) and not self.approve:
            raise UserError(_("La membresía está revocada: actívela para asignar accesos."))
        if self.approve and membership.state in ("requested", "invited", "suspended", "revoked"):
            membership.action_approve() if membership.state != "revoked" else membership.write({"state": "active"})
        existing = {(g.role_id.id) for g in membership.grant_ids if g.active_now}
        for role in self.role_ids:
            if role.id in existing:
                continue
            self.env["step.app.grant"].create({
                "membership_id": membership.id, "module_id": role.module_id.id, "role_id": role.id,
                "valid_from": self.valid_from or False, "valid_to": self.valid_to or False})
        return {"type": "ir.actions.act_window_close"}
