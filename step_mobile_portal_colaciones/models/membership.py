from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class StepAppMembership(models.Model):
    _inherit = "step.app.membership"

    employee_id = fields.Many2one(
        "hr.employee", string="Trabajador vinculado", tracking=True, index=True,
        help="Vínculo explícito con el trabajador que consulta sus colaciones. Nunca se asigna por nombre o correo coincidente.")

    @api.constrains("employee_id", "company_id", "state")
    def _check_employee_link(self):
        for rec in self.filtered("employee_id"):
            if rec.employee_id.company_id != rec.company_id:
                raise ValidationError(_("El trabajador pertenece a otra empresa."))
            other = self.sudo().search([("employee_id", "=", rec.employee_id.id), ("id", "!=", rec.id),
                                        ("state", "in", ("active", "suspended", "invited"))], limit=1)
            if other and rec.state in ("active", "suspended", "invited"):
                raise ValidationError(_("Ese trabajador ya está vinculado a otra persona."))

    def write(self, vals):
        before = {rec.id: rec.employee_id.id for rec in self}
        res = super().write(vals)
        if "employee_id" in vals:
            for rec in self:
                if rec.employee_id.id != before[rec.id]:
                    rec._audit("membership_employee_link", detail="trabajador %s → %s" % (before[rec.id] or "-", rec.employee_id.id or "-"))
        return res
