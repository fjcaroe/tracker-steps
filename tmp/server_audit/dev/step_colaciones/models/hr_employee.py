from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    meal_eligible = fields.Boolean(
        string="Tiene colación",
        default=False,
        help="Permite que el trabajador se registre en un tótem de colaciones.",
        index=True,
    )
    meal_nfc_uid = fields.Char(
        string="Identificador NFC",
        copy=False,
        groups="hr.group_hr_user",
        help="UID leído por el lector NFC. Debe ser único dentro de la empresa.",
    )
    meal_distribution_mode = fields.Selection(
        [
            ("fixed", "Distribución fija"),
            ("dynamic", "Distribución dinámica según horas"),
        ],
        string="Distribución de colaciones",
        default="fixed",
        required=True,
        help=(
            "La distribución dinámica usa las horas del día registradas en "
            "Actividades. Si no existen, utiliza la distribución fija."
        ),
    )
    meal_analytic_distribution = fields.Json(
        string="Distribución analítica fija",
        copy=True,
        help="Distribución que se usa siempre en modo fijo y como respaldo del modo dinámico.",
    )
    analytic_precision = fields.Integer(
        store=False,
        default=lambda self: self.env["decimal.precision"].precision_get("Percentage Analytic"),
    )

    @api.constrains("meal_analytic_distribution", "company_id")
    def _check_meal_analytic_distribution(self):
        for employee in self.filtered("meal_analytic_distribution"):
            distribution = employee.meal_analytic_distribution or {}
            if abs(sum(float(value) for value in distribution.values()) - 100.0) > 0.01:
                raise ValidationError(_(
                    "La distribución analítica fija de colaciones debe sumar 100%%."
                ))
            account_ids = {
                int(account_id)
                for key in distribution
                for account_id in str(key).split(",")
                if str(account_id).isdigit()
            }
            accounts = self.env["account.analytic.account"].browse(account_ids).exists()
            if len(accounts) != len(account_ids):
                raise ValidationError(_("La distribución contiene una cuenta analítica inexistente."))
            invalid = accounts.filtered(
                lambda account: account.company_id and account.company_id != employee.company_id
            )
            if invalid:
                raise ValidationError(_(
                    "Todas las cuentas analíticas de colaciones deben pertenecer a la compañía del trabajador."
                ))

    @api.constrains("meal_nfc_uid", "company_id", "active")
    def _check_unique_meal_nfc_uid(self):
        for employee in self.filtered(lambda rec: rec.active and rec.meal_nfc_uid):
            duplicate = self.sudo().search_count([
                ("id", "!=", employee.id),
                ("active", "=", True),
                ("company_id", "=", employee.company_id.id),
                ("meal_nfc_uid", "=", employee.meal_nfc_uid.strip()),
            ])
            if duplicate:
                raise ValidationError(_("El identificador NFC ya está asignado a otro trabajador."))

    @api.onchange("meal_nfc_uid")
    def _onchange_meal_nfc_uid(self):
        if self.meal_nfc_uid:
            self.meal_nfc_uid = self.meal_nfc_uid.strip()
