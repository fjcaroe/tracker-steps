import json
from lxml import etree
from odoo import api, models, _
from odoo.exceptions import UserError


class View(models.Model):
    _inherit = 'ir.ui.view'

    @api.model
    def _step_repair_legacy_view_references(self):
        archive=self.env['step.payroll.legacy.snapshot'].sudo()

        def save(view, arch):
            if not archive.search_count([('source_model','=','ir.ui.view'),('source_id','=',view.id)]):
                archive.create({'source_model':'ir.ui.view','source_id':view.id,'payload':{'arch':view.arch_db}})
            view.with_context(lang=None).write({'arch_db':etree.tostring(arch,encoding='unicode')})

        def detach_epp_layout(view, root):
            # An EPP document replaced the article of EVERY standard report.
            # Keep that design as a dedicated layout used only by its model.
            snapshot=archive.search([('source_model','=','ir.ui.view'),('source_id','=',view.id)],limit=1)
            original=snapshot.payload['arch'] if snapshot else view.with_context(lang=None).arch_db
            if not snapshot:
                archive.create({'source_model':'ir.ui.view','source_id':view.id,'payload':{'arch':original}})
            def template(key, parent, content):
                xmlid='step_environment_policy.'+key
                existing=self.env.ref(xmlid,raise_if_not_found=False)
                if existing: return existing
                created=self.sudo().create({'name':key,'key':xmlid,'type':'qweb','mode':'primary','inherit_id':parent.id,'arch_db':content})
                self.env['ir.model.data'].sudo().create({'module':'step_environment_policy','name':key,'model':'ir.ui.view','res_id':created.id,'noupdate':True})
                return created
            layout=template('legacy_epp_layout',root,original)
            wrapper=template('legacy_epp_external',self.env.ref('web.external_layout'),'<data><xpath expr="//t[@t-call]" position="attributes"><attribute name="t-call">step_environment_policy.legacy_epp_layout</attribute></xpath></data>')
            models=[name for name,model in self.env.registry.models.items() if 'x_studio_one2many_field_26t_1jhjvls6e' in model._fields]
            for report in self.env['ir.actions.report'].sudo().search([('model','in',models)]):
                report_view=self.env.ref(report.report_name,raise_if_not_found=False) or self.search([('key','=',report.report_name)],limit=1)
                if report_view:
                    report_arch=etree.fromstring(report_view.with_context(lang=None).arch_db)
                    calls=report_arch.xpath('//*[@t-call="web.external_layout"]')
                    for node in calls: node.set('t-call','step_environment_policy.legacy_epp_external')
                    if calls: save(report_view,report_arch)
            view.write({'active':False})

        roots=[self.env.ref(x,raise_if_not_found=False) for x in ('web.external_layout_standard','web.external_layout_boxed','web.external_layout_bold','web.external_layout_striped','web.external_layout_wave')]
        layouts=self.sudo().browse([v.id for v in roots if v])
        while True:
            descendants=self.sudo().search([('active','=',True),('inherit_id','in',layouts.ids)])
            newer=layouts | descendants
            if newer==layouts: break
            layouts=newer
        for view in layouts:
            arch=etree.fromstring(view.with_context(lang=None).arch_db)
            if view.mode=='extension' and 'x_studio_one2many_field_26t_1jhjvls6e' in view.arch_db and 'doc.x_' in view.arch_db:
                detach_epp_layout(view,self.env.ref('web.external_layout_standard'))
                continue
            if view.mode=='primary' and view.id not in [v.id for v in roots if v]:
                continue
            nodes=arch.xpath('//*[@t-field="doc.x_name"]')
            for node in nodes: node.set('t-field','company.name')
            if nodes: save(view,arch)
        owned=self.env['ir.model.data'].sudo().search([('module','=','studio_customization'),('model','=','ir.ui.view')]).mapped('res_id')
        for view in self.sudo().browse(owned).exists().filtered(lambda v:v.active and v.model=='hr.employee'):
            arch=etree.fromstring(view.with_context(lang=None).arch_db)
            changed=False
            for field in arch.xpath('//field[@name]'):
                metadata=self.env['hr.employee']._fields.get(field.get('name'))
                if not metadata or getattr(metadata,'comodel_name',None)!='step.work.schedule':
                    continue
                for nested in list(field):
                    if nested.tag in ('list','tree','form') and nested.xpath('.//field[@name="employee_id"]'):
                        field.remove(nested)
                        changed=True
            if changed: save(view,arch)
        return True


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
