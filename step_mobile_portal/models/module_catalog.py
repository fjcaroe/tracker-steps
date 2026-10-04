from odoo import api, fields, models
from odoo.exceptions import ValidationError


class StepAppModule(models.Model):
    _name = "step.app.module"
    _description = "Módulo de la aplicación Steps"
    _order = "sequence, code"

    code = fields.Char(required=True, index=True, help="Identificador estable. La aplicación lo usa para enlazar el manifiesto del módulo.")
    name = fields.Char(required=True, translate=True)
    icon = fields.Char(default="apps")
    sequence = fields.Integer(default=10)
    contract_version = fields.Integer(
        required=True, default=1,
        help="Versión del contrato servidor↔app del módulo. Solo se ofrece a aplicaciones que declaran soportarla.")
    min_app_version = fields.Char(default="1.0.0")
    active = fields.Boolean(default=True)
    role_ids = fields.One2many("step.app.module.role", "module_id", string="Roles")

    _sql_constraints = [("code_unique", "unique(code)", "El código del módulo debe ser único.")]


class StepAppModuleRole(models.Model):
    _name = "step.app.module.role"
    _description = "Rol de un módulo de Steps App"
    _order = "module_id, code"

    module_id = fields.Many2one("step.app.module", required=True, ondelete="cascade", index=True)
    code = fields.Char(required=True)
    name = fields.Char(required=True, translate=True)
    permissions = fields.Char(
        required=True, help="Permisos separados por coma, p. ej. «colaciones.register». El servidor los valida en cada llamada.")

    _sql_constraints = [("module_code_unique", "unique(module_id, code)", "El rol ya existe en este módulo.")]

    @api.constrains("permissions")
    def _check_permissions(self):
        for role in self:
            if not role.permission_list():
                raise ValidationError("Indique al menos un permiso.")

    def permission_list(self):
        self.ensure_one()
        return [p.strip() for p in (self.permissions or "").split(",") if p.strip()]
