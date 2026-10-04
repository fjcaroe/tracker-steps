from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class StepAppGrant(models.Model):
    _name = "step.app.grant"
    _description = "Concesión de módulo y rol"
    _order = "membership_id, module_id"

    membership_id = fields.Many2one("step.app.membership", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="membership_id.company_id", store=True, index=True)
    person_id = fields.Many2one(related="membership_id.person_id", store=True, index=True)
    module_id = fields.Many2one("step.app.module", required=True, index=True)
    role_id = fields.Many2one("step.app.module.role", required=True, domain="[('module_id', '=', module_id)]")
    valid_from = fields.Datetime()
    valid_to = fields.Datetime()
    revoked_at = fields.Datetime(readonly=True, copy=False,
                                 help="Una concesión nunca se borra: al revocarse conserva su historia.")
    scope_ids = fields.Json(string="Alcance (IDs)", help="Lista de IDs de recursos del módulo a los que se limita la concesión. Vacío: toda la empresa.")
    active_now = fields.Boolean(compute="_compute_active_now", string="Vigente")

    @api.depends("valid_from", "valid_to", "revoked_at", "membership_id.state")
    def _compute_active_now(self):
        now = fields.Datetime.now()
        for grant in self:
            grant.active_now = bool(
                grant.membership_id.state == "active" and not (grant.revoked_at and grant.revoked_at <= now)
                and (not grant.valid_from or grant.valid_from <= now) and (not grant.valid_to or now < grant.valid_to))

    @api.constrains("module_id", "role_id")
    def _check_role_module(self):
        for grant in self:
            if grant.role_id.module_id != grant.module_id:
                raise ValidationError(_("El rol no pertenece al módulo."))

    @api.constrains("valid_from", "valid_to")
    def _check_dates(self):
        for grant in self:
            if grant.valid_from and grant.valid_to and grant.valid_to <= grant.valid_from:
                raise ValidationError(_("La vigencia termina antes de comenzar."))

    @api.constrains("scope_ids")
    def _check_scope(self):
        for grant in self:
            scope = grant.scope_ids
            if scope and not (isinstance(scope, list) and all(isinstance(i, int) for i in scope)):
                raise ValidationError(_("El alcance debe ser una lista de números."))

    @api.model_create_multi
    def create(self, vals_list):
        grants = super().create(vals_list)
        for grant in grants:
            self.env["step.app.audit"].log(
                "grant_created", person=grant.person_id, company=grant.company_id,
                detail="%s/%s" % (grant.module_id.code, grant.role_id.code))
        return grants

    def write(self, vals):
        tracked = {"valid_from", "valid_to", "role_id", "module_id", "scope_ids", "revoked_at"}
        res = super().write(vals)
        if tracked & set(vals):
            for grant in self:
                self.env["step.app.audit"].log(
                    "grant_changed", person=grant.person_id, company=grant.company_id,
                    detail="%s/%s %s" % (grant.module_id.code, grant.role_id.code, sorted(tracked & set(vals))))
        return res

    def unlink(self):
        raise ValidationError(_("Las concesiones no se borran; use «Revocar»."))

    def action_revoke(self):
        self.filtered(lambda g: not g.revoked_at).write({"revoked_at": fields.Datetime.now()})
