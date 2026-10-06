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
    def _step_normalize_agriculture_menus(self):
        """Keep previous screens recoverable, separate from native operations."""
        Model = self.sudo().with_context(active_test=False)

        def history(root, key):
            xmlid = 'step_environment_policy.' + key
            menu = self.env.ref(xmlid, raise_if_not_found=False)
            if not menu:
                menu = Model.create({'name': _('Historial anterior'), 'parent_id':root.id, 'sequence':95,
                                     'groups_id':[(6,0,[self.env.ref('base.group_system').id])]})
                self.env['ir.model.data'].sudo().create({'module':'step_environment_policy','name':key,'model':'ir.ui.menu','res_id':menu.id,'noupdate':True})
            return menu

        packing = self.env.ref('step_packing_operations.menu_packing_operations_root', raise_if_not_found=False)
        if packing:
            parent = history(packing,'packing_history')
            for xmlid in ('step_packing.menu_step_packing_root','step_packing.menu_packing_fruta_root'):
                old = self.env.ref(xmlid,raise_if_not_found=False)
                if old and old != packing:
                    old.write({'parent_id':parent.id})
        cosecha = self.env.ref('step_cosecha.menu_step_cosecha_root',raise_if_not_found=False)
        if cosecha:
            menus=Model.search([('id','child_of',cosecha.id)])
            studio_ids=self.env['ir.model.data'].sudo().search([('module','=','studio_customization'),('model','=','ir.ui.menu'),('res_id','in',menus.ids)]).mapped('res_id')
            if studio_ids:
                parent=history(cosecha,'harvest_history')
                for old in Model.browse(studio_ids):
                    if old.parent_id.id not in studio_ids:
                        old.write({'parent_id':parent.id})
            master_parent=self.env.ref('step_cosecha.menu_parametro_gnl_cosecha',raise_if_not_found=False)
            if master_parent:
                for suffix,label in (('temporada','Temporadas'),('especie','Especies'),('grupo_variedad','Grupos de variedades'),('variedad','Variedades')):
                    action=self.env.ref('step_hr.action_step_'+suffix,raise_if_not_found=False)
                    key='harvest_master_'+suffix
                    if action and not self.env.ref('step_environment_policy.'+key,raise_if_not_found=False):
                        menu=Model.create({'name':label,'parent_id':master_parent.id,'action':'ir.actions.act_window,%s'%action.id,'sequence':50})
                        self.env['ir.model.data'].sudo().create({'module':'step_environment_policy','name':key,'model':'ir.ui.menu','res_id':menu.id,'noupdate':True})
        return True

    @api.model
    def _visible_menu_ids(self, debug=False):
        visible = super()._visible_menu_ids(debug)
        configured = self.env['ir.config_parameter'].sudo().get_param('steps.environment.menu_root_xmlids')
        if not configured:
            return visible
        roots = [self.env.ref(xmlid, raise_if_not_found=False) for xmlid in json.loads(configured)]
        allowed = self.sudo().with_context(active_test=False).search([('id','child_of',[r.id for r in roots if r])])
        return visible & set(allowed.ids)
