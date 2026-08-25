from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..tools import dt_book


class ResCompany(models.Model):
    _inherit = "res.company"

    remuneration_book_profile_id = fields.Many2one(
        "step.remuneration.book.profile",
        string="Perfil del Libro de Remuneraciones",
        domain="[('state', '=', 'active'), "
               "'|', ('company_id', '=', False), ('company_id', '=', id)]",
        help="Mapeo entre códigos DT y reglas salariales. Sólo se pueden "
             "asignar perfiles Activos. Si se deja vacío se intenta detectar "
             "uno único a partir de las liquidaciones del período.",
    )
    remuneration_book_tolerance = fields.Integer(
        string="Tolerancia de conciliación (pesos)",
        default=dt_book.DEFAULT_TOLERANCE,
        help="Diferencia máxima admitida entre los totales oficiales y la suma "
             "de las columnas visibles antes de emitir una advertencia. `0` "
             "significa tolerancia estricta. Es un criterio de revisión "
             "interna, no una regla legal.",
    )

    _sql_constraints = [
        ("remuneration_book_tolerance_positive",
         "CHECK(remuneration_book_tolerance >= 0)",
         "La tolerancia de conciliación debe ser un entero mayor o igual a "
         "cero."),
    ]

    @api.constrains("remuneration_book_tolerance")
    def _check_remuneration_book_tolerance(self):
        for company in self:
            if (company.remuneration_book_tolerance or 0) < 0:
                raise ValidationError(_(
                    "La tolerancia de conciliación no puede ser negativa. Use "
                    "`0` para exigir coincidencia exacta."))
