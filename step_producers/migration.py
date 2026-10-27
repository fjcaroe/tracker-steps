"""Preserve the original window binding when replacing a read-only Gantt view."""
from odoo.exceptions import UserError


def adopt_calendar_binding(env, module):
    if module not in ('step_producer_contract_report', 'step_producer_estimate_report'):
        raise UserError('Informe fuera del alcance de la migración de calendario.')
    action = env.ref(module + '.report_action')
    view = env.ref(module + '.report_gantt')
    bindings = action.view_ids.filtered(lambda row: row.view_id == view)
    if len(bindings) != 1 or bindings.view_mode not in ('gantt', 'calendar'):
        raise UserError('El informe debe conservar un único enlace de calendario compatible.')
    if action.view_ids.filtered(lambda row: row != bindings and row.view_mode == 'calendar'):
        raise UserError('Existe un calendario adicional; revisar la configuración antes de migrar.')
    bindings.view_mode = 'calendar'
