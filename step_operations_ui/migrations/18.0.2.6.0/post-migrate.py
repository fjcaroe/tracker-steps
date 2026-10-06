"""Make all freight actions/bookmarks resolve to the native code forms."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for model, prefix in (('step.freight.route', 'route'), ('step.freight.cold.mode', 'cold_mode'),
                          ('step.freight.tariff', 'tariff_code'), ('step.freight.order', 'order_code')):
        form = env.ref(f'step_operations_ui.view_freight_{prefix}_form')
        for action in env['ir.actions.act_window'].search([('res_model', '=', model)]):
            action.view_ids.filtered(lambda item: item.view_id and not item.view_id.active).unlink()
            if action.view_id and not action.view_id.active:
                action.view_id = False
            if action.search_view_id and not action.search_view_id.active:
                action.search_view_id = False
            # Bind form explicitly, so a nested Create and edit action and an
            # old bookmark cannot accidentally select a different master.
            binding = action.view_ids.filtered(lambda item: item.view_mode == 'form')
            if binding:
                binding.write({'view_id': form.id})
            else:
                env['ir.actions.act_window.view'].create({
                    'act_window_id': action.id, 'view_mode': 'form', 'view_id': form.id, 'sequence': 10})
