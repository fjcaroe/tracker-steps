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
    # The parent's new arch is validated before dependent addons reload their
    # XML. Move this existing owned child xpath in the same migration transaction
    # so it does not still target <gantt> while its parent becomes <calendar>.
    prefix = 'contract' if module == 'step_producer_contract_report' else 'estimate'
    child = env.ref('step_producer_purchase_mode.' + prefix + '_gantt', raise_if_not_found=False)
    if child:
        if child.inherit_id != view:
            raise UserError('La vista de modalidad tiene un padre diferente; revisar antes de migrar.')
        env.cr.execute("""UPDATE ir_ui_view SET type='calendar', arch_db=(
            SELECT jsonb_object_agg(key,replace(value,'//gantt/','//calendar/'))
            FROM jsonb_each_text(arch_db)) WHERE id=%s""", [child.id])
        child.invalidate_recordset()
        env.registry.clear_cache()
    bindings.view_mode = 'calendar'
