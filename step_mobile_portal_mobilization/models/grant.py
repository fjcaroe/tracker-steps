from odoo import _, api, models
from odoo.exceptions import ValidationError


class StepAppGrant(models.Model):
    _inherit = "step.app.grant"

    @api.constrains("role_id", "membership_id")
    def _check_driver_link(self):
        """El rol de conductor exige un vínculo explícito con un contacto marcado como chofer de la misma empresa."""
        for grant in self.filtered(lambda g: g.module_id.code == "mobilization" and g.role_id.code == "conductor"):
            partner = grant.membership_id.partner_id
            if not partner or not partner.step_chofer:
                raise ValidationError(_("Para ser conductor, vincule primero la membresía con un contacto marcado como chofer."))
