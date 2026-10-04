from odoo import api, fields, models
from odoo.exceptions import UserError


class StepAppAudit(models.Model):
    _name = "step.app.audit"
    _description = "Auditoría de accesos de Steps App"
    _order = "id desc"

    date = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    user_id = fields.Many2one("res.users", string="Usuario Odoo", default=lambda self: self.env.user)
    person_id = fields.Many2one("step.app.person", index=True, ondelete="set null")
    company_id = fields.Many2one("res.company", index=True)
    action = fields.Char(required=True, index=True)
    detail = fields.Text()

    @api.model
    def log(self, action, person=None, company=None, detail=""):
        return self.sudo().create({
            "action": action, "person_id": person.id if person else False,
            "company_id": company.id if company else False, "detail": detail or False,
            "user_id": self.env.user.id if not self.env.user._is_public() else False,
        })

    def write(self, vals):
        raise UserError("La auditoría es de solo lectura.")

    def unlink(self):
        raise UserError("La auditoría no se borra.")
