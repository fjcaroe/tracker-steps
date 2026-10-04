import secrets
import uuid

from odoo import fields, models

_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _org_code():
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))


class ResCompany(models.Model):
    _inherit = "res.company"

    step_app_org_uid = fields.Char(
        string="Identificador de organización (Steps App)", copy=False, index=True, readonly=True,
        default=lambda self: str(uuid.uuid4()),
        help="Identificador estable de esta empresa en la aplicación. Los IDs locales de Odoo no son identidades globales.")
    step_app_org_code = fields.Char(
        string="Código de acceso (Steps App)", copy=False, default=lambda self: _org_code(),
        help="Código corto que una persona registrada puede usar para solicitar acceso a esta empresa. No otorga acceso por sí solo.")
    step_app_offline_hours = fields.Integer(
        string="Autorización sin conexión (horas)", default=72,
        help="Tiempo máximo que un teléfono validado puede operar sin volver a consultar permisos.")

    _sql_constraints = [
        ("step_app_org_uid_unique", "unique(step_app_org_uid)", "El identificador de organización debe ser único."),
        ("step_app_org_code_unique", "unique(step_app_org_code)", "El código de acceso debe ser único."),
        ("step_app_offline_hours_range", "check(step_app_offline_hours between 1 and 720)",
         "La autorización sin conexión debe estar entre 1 y 720 horas."),
    ]

    def action_step_app_regenerate_code(self):
        for company in self:
            company.step_app_org_code = _org_code()
