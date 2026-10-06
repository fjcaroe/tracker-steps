"""Retire only the two migrated masters' Studio views and keep old links usable."""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for model, prefix in (('x_tramo_de_flete', 'route'), ('x_modalidad_de_frio', 'cold_mode')):
        data = env['ir.model.data'].search([
            ('module', '=', 'studio_customization'), ('model', '=', 'ir.ui.view')])
        studio_views = env['ir.ui.view'].browse(data.mapped('res_id')).exists().filtered(
            lambda view: view.model == model)
        studio_views.write({'active': False})
        list_view = env.ref(f'step_operations_ui.view_freight_{prefix}_list')
        search_view = env.ref(f'step_operations_ui.view_freight_{prefix}_search')
        actions = env['ir.actions.act_window'].search([('res_model', '=', model)])
        # Existing bookmarks/menus keep their action IDs. Their default forms
        # now resolve to the code view, including Studio-created old actions.
        for action in actions:
            action.view_ids.filtered(lambda item: item.view_id in studio_views).unlink()
            action.write({'view_id': list_view.id, 'search_view_id': search_view.id,
                          'view_mode': 'list,form'})
