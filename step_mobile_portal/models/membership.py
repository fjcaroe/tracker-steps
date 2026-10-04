from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class StepAppMembership(models.Model):
    _name = "step.app.membership"
    _description = "Membresía de una persona en una empresa"
    _inherit = ["mail.thread"]
    _order = "company_id, person_id"

    person_id = fields.Many2one("step.app.person", required=True, ondelete="cascade", index=True, tracking=True)
    company_id = fields.Many2one("res.company", required=True, index=True, tracking=True, default=lambda self: self.env.company)
    state = fields.Selection(
        [("invited", "Invitada"), ("requested", "Solicitada"), ("active", "Activa"), ("suspended", "Suspendida"), ("revoked", "Revocada")],
        default="requested", required=True, tracking=True, index=True)
    valid_from = fields.Datetime(tracking=True)
    valid_to = fields.Datetime(tracking=True)
    partner_id = fields.Many2one(
        "res.partner", string="Contacto / conductor vinculado", tracking=True,
        help="Vínculo explícito con un contacto existente (p. ej. conductor). Nunca se asigna por nombre o correo coincidente.")
    request_note = fields.Text(readonly=True)
    grant_ids = fields.One2many("step.app.grant", "membership_id", string="Concesiones")

    _sql_constraints = [("person_company_unique", "unique(person_id, company_id)", "La persona ya tiene una membresía en esta empresa.")]

    @api.constrains("valid_from", "valid_to")
    def _check_dates(self):
        for rec in self:
            if rec.valid_from and rec.valid_to and rec.valid_to <= rec.valid_from:
                raise ValidationError(_("La vigencia termina antes de comenzar."))

    @api.constrains("partner_id", "company_id", "state")
    def _check_partner_link(self):
        for rec in self.filtered("partner_id"):
            if rec.partner_id.company_id and rec.partner_id.company_id != rec.company_id:
                raise ValidationError(_("El contacto pertenece a otra empresa."))
            other = self.sudo().search([("partner_id", "=", rec.partner_id.id), ("company_id", "=", rec.company_id.id),
                                        ("state", "in", ("active", "suspended", "invited")), ("id", "!=", rec.id)], limit=1)
            if other and rec.state in ("active", "suspended", "invited"):
                raise ValidationError(_("Ese contacto ya está vinculado a otra persona de esta empresa."))

    def _audit(self, action, detail=""):
        for rec in self:
            self.env["step.app.audit"].log(action, person=rec.person_id, company=rec.company_id, detail=detail)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._audit("membership_created", detail=", ".join(records.mapped("state")))
        return records

    def write(self, vals):
        before = {rec.id: (rec.state, rec.partner_id.id) for rec in self}
        res = super().write(vals)
        for rec in self:
            old_state, old_partner = before[rec.id]
            if rec.state != old_state:
                rec._audit("membership_state", detail="%s → %s" % (old_state, rec.state))
            if rec.partner_id.id != old_partner:
                rec._audit("membership_link", detail="contacto %s → %s" % (old_partner or "-", rec.partner_id.id or "-"))
        return res

    def action_approve(self):
        for rec in self:
            if rec.state not in ("requested", "invited", "suspended"):
                raise UserError(_("Solo se aprueba una membresía solicitada, invitada o suspendida."))
        self.write({"state": "active"})

    def action_suspend(self):
        self.write({"state": "suspended"})

    def action_revoke(self):
        """Revoca la membresía y todas sus concesiones; conserva la historia para evaluar eventos capturados antes."""
        now = fields.Datetime.now()
        self.write({"state": "revoked"})
        self.mapped("grant_ids").filtered(lambda g: not g.revoked_at).write({"revoked_at": now})
