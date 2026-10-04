from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class StepAppPerson(models.Model):
    _name = "step.app.person"
    _description = "Persona de la aplicación Steps"
    _inherit = ["mail.thread"]
    _order = "name"

    name = fields.Char(required=True, tracking=True)
    email = fields.Char(index=True, help="Correo informado al registrarse. No identifica la cuenta ni vincula con empleados.")
    state = fields.Selection(
        [("active", "Activa"), ("suspended", "Suspendida"), ("deletion_requested", "Eliminación solicitada"), ("closed", "Cerrada")],
        default="active", required=True, tracking=True, index=True)
    identity_ids = fields.One2many("step.app.identity", "person_id", string="Identidades")
    membership_ids = fields.One2many("step.app.membership", "person_id", string="Membresías")
    device_ids = fields.One2many("step.app.device", "person_id", string="Dispositivos")
    deletion_requested_at = fields.Datetime(readonly=True)
    provider_summary = fields.Char(compute="_compute_provider_summary")

    @api.depends("identity_ids.provider")
    def _compute_provider_summary(self):
        for person in self:
            person.provider_summary = ", ".join(sorted(set(person.identity_ids.mapped("provider"))))

    def _audit(self, action, detail="", company=None):
        for person in self:
            self.env["step.app.audit"].log(action, person=person, company=company, detail=detail)

    def action_suspend(self):
        self.write({"state": "suspended"})
        self._revoke_sessions("account_suspended")
        self._audit("person_suspended")

    def action_reactivate(self):
        for person in self:
            if person.state == "closed":
                raise UserError(_("Una cuenta cerrada no se reactiva."))
        self.write({"state": "active"})
        self._audit("person_reactivated")

    def _check_admin_scope(self):
        """Un administrador de empresa solo cierra sesiones de personas cuyos accesos están todos en SUS empresas;
        si la persona trabaja también en otra empresa, lo decide un administrador del sistema."""
        if self.env.user.has_group("base.group_system"):
            return
        mine = self.env.user.company_ids
        for person in self.sudo():
            foreign = person.membership_ids.filtered(lambda m: m.state in ("active", "suspended", "invited", "requested")).company_id - mine
            if foreign:
                raise AccessError(_("%(name)s tiene accesos en otras empresas: pida a un administrador del sistema.", name=person.name))

    def action_revoke_sessions(self):
        self._check_admin_scope()
        self._revoke_sessions("revoked_by_admin")
        self._audit("sessions_revoked")

    def _revoke_sessions(self, reason):
        sessions = self.env["step.app.session"].sudo().search([("person_id", "in", self.ids), ("revoked_at", "=", False)])
        sessions.write({"revoked_at": fields.Datetime.now(), "revoked_reason": reason})

    def request_deletion(self):
        """Elimina la posibilidad de entrar. Los registros empresariales (colaciones, viajes) se conservan bajo la política de cada empresa."""
        now = fields.Datetime.now()
        for person in self:
            person.sudo().write({"state": "deletion_requested", "deletion_requested_at": now})
            person.sudo().identity_ids.write({"secret_hash": False, "locked_until": False})
            person.sudo().membership_ids.filtered(lambda m: m.state in ("active", "invited", "requested")).write({"state": "revoked"})
        self._revoke_sessions("deletion_requested")
        self._audit("deletion_requested", detail="Identidad y accesos retirados; registros empresariales conservados.")
