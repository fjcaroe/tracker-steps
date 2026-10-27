"""Calendar Date ends are inclusive; retain original exclusive SQL boundaries."""
from odoo import fields, _
from odoo.exceptions import UserError


def inclusive_end_domain(source_field, operator, value):
    if source_field not in ('date_stop', 'week_end'):
        raise UserError(_('Fecha de calendario fuera del alcance del informe.'))
    if operator == '=?':
        if not value:
            return []
        operator = '='
    def shifted(date):
        return fields.Date.add(fields.Date.to_date(date), days=1) if date else False
    if operator in ('in', 'not in'):
        return [(source_field, operator, [shifted(date) for date in value])]
    if operator not in ('=', '!=', '>', '>=', '<', '<='):
        raise UserError(_('Operador no válido para una fecha de calendario.'))
    return [(source_field, operator, shifted(value))]
