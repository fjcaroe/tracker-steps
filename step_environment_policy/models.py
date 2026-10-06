import json
from odoo import api, models, _
from odoo.exceptions import UserError


class Module(models.Model):
    _inherit = 'ir.module.module'

    def button_install(self):
        official = self.env['ir.config_parameter'].sudo().get_param('steps.environment.payroll_engine')
        if official == 'l10n_cl_simpledigital_payroll':
            pending, seen = set(self.mapped('name')), set()
            while pending:
                name = pending.pop()
                if name in seen:
                    continue
                seen.add(name)
                if name.startswith('l10n_cl_hr') or name in ('step_hr_previred_blueminds','step_hr_contract_lifecycle_agriculture'):
                    raise UserError(_('El motor oficial es Simple Digital. El motor anterior fue retirado y no se puede reinstalar.'))
                module = self.search([('name','=',name)])
                pending.update(set(module.dependencies_id.mapped('name')) - seen)
        return super().button_install()


class Menu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _visible_menu_ids(self, debug=False):
        visible = super()._visible_menu_ids(debug)
        configured = self.env['ir.config_parameter'].sudo().get_param('steps.environment.menu_root_xmlids')
        if not configured:
            return visible
        roots = [self.env.ref(xmlid, raise_if_not_found=False) for xmlid in json.loads(configured)]
        allowed = self.sudo().with_context(active_test=False).search([('id','child_of',[r.id for r in roots if r])])
        return visible & set(allowed.ids)
