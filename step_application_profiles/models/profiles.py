from odoo import api, models, _
from odoo.exceptions import AccessError

APPS=('packing','export','producers')
LEVELS=('read','operation','manager')
SHARED_EXPORT=('step.export.stock.reservation','step.export.dispatch.order','step.export.shipping.instruction',
               'step.export.packing.list','step.export.export')
LOOKUPS=('step.producer.purchase.contract','step.export.sales.program','step.export.packaging.program')
MASTERS=('res.partner','step.fundo','step.especie','step.variedad','step.grupo.variedad','step.temporada')


def owners(model):
    if model=='step.fruit.package.line':return {'packing','export'}
    if model.startswith(SHARED_EXPORT):return {'packing','export'}
    if model.startswith(('step.producer.','step.export.producer.','step.export.grower.','step.export.estimate')):
        return {'producers'}
    if model.startswith(('step.packing.','step.fruit.','step.harvest.container.','step.scale.')):return {'packing'}
    if model.startswith('step.export.'):return {'export'}
    return set()


def shared_model(model):
    return model.startswith(('stock.','product.','mrp.bom')) or model in MASTERS


class Users(models.Model):
    _inherit='res.users'

    def _step_application_levels(self):
        self.ensure_one()
        # env.user is a sudo record even when the calling model is not sudo.
        # Callers must test their own environment, not this record's su flag.
        if self.has_group('base.group_system'):return None
        levels={app:max((i for i,level in enumerate(LEVELS,1)
                        if self.has_group('step_application_profiles.%s_%s'%(app,level))),default=0) for app in APPS}
        return levels if any(levels.values()) else None


class ModelAccess(models.Model):
    _inherit='ir.model.access'

    @api.model
    def check(self,model,mode='read',raise_exception=True):
        permitted=super().check(model,mode=mode,raise_exception=raise_exception)
        if not permitted or self.env.su:return permitted
        apps=owners(model)
        if not apps and not shared_model(model):return permitted
        levels=self.env.user._step_application_levels()
        if levels is None:return permitted
        if apps:
            level=max(levels[app] for app in apps)
            dependency=mode=='read' and model.startswith(LOOKUPS)
            detail=(model.endswith(('.line','.product','.installment','.week','.consumption','.downtime')))
            required=1 if mode=='read' else 2 if mode in ('create','write') or detail else 3
            permitted=dependency or level>=required
        elif mode!='read':
            is_master=model in MASTERS or model.startswith(('product.','mrp.bom'))
            permitted=max(levels.values())>=(3 if is_master else 2)
            if model.startswith(('stock.','product.','mrp.bom')) and self.env.user.has_group('stock.group_stock_manager'):
                permitted=True
        if not permitted and raise_exception:
            raise AccessError(_('El perfil de aplicación no permite esta operación. Solicite el nivel apropiado al administrador.'))
        return bool(permitted)


class Menu(models.Model):
    _inherit='ir.ui.menu'

    @api.model
    def _visible_menu_ids(self,debug=False):
        visible=super()._visible_menu_ids(debug=debug)
        if self.env.su:return visible
        levels=self.env.user._step_application_levels()
        if levels is None:return visible
        blocked=self.browse()
        roots={'packing':'step_packing_operations.menu_packing_operations_root',
               'export':'step_export.menu_step_export_root','producers':'step_producers.menu_step_producers_root'}
        for app,xmlid in roots.items():
            root=self.env.ref(xmlid,raise_if_not_found=False)
            if root and not levels[app]:blocked|=root
        if not blocked:return visible
        descendants=self.sudo().search([('id','child_of',blocked.ids)])
        return set(visible)-set(descendants.ids)


def require_fruit_operation(env,kind):
    if env.su:return
    levels=env.user._step_application_levels()
    if levels is not None and max(levels[app] for app in (('packing',) if kind=='C' else ('packing','export')))<2:
        raise AccessError(_('El perfil no permite modificar esta recepción o tarja de fruta.'))


class Picking(models.Model):
    _inherit='stock.picking'

    @api.model_create_multi
    def create(self,values):
        if any(row.get('step_fruit_reception_kind') for row in values):require_fruit_operation(self.env,'C')
        return super().create(values)

    def write(self,values):
        if values.get('step_fruit_reception_kind') or any(self.mapped('step_fruit_reception_kind')):require_fruit_operation(self.env,'C')
        return super().write(values)

    def button_validate(self):
        if any(self.mapped('step_fruit_reception_kind')):require_fruit_operation(self.env,'C')
        return super().button_validate()


class Package(models.Model):
    _inherit='stock.quant.package'

    @api.model_create_multi
    def create(self,values):
        for row in values:
            if row.get('is_fruit_tag'):require_fruit_operation(self.env,row.get('step_tag_kind'))
        return super().create(values)

    def write(self,values):
        for package in self.filtered('is_fruit_tag'):require_fruit_operation(self.env,package.step_tag_kind)
        if values.get('is_fruit_tag') or values.get('step_tag_kind'):require_fruit_operation(self.env,values.get('step_tag_kind'))
        return super().write(values)


class PackageLine(models.Model):
    _inherit='step.fruit.package.line'

    @api.model_create_multi
    def create(self,values):
        for package in self.env['stock.quant.package'].browse([row['package_id'] for row in values if row.get('package_id')]):
            require_fruit_operation(self.env,package.step_tag_kind)
        return super().create(values)

    def write(self,values):
        for package in self.package_id:require_fruit_operation(self.env,package.step_tag_kind)
        return super().write(values)

    def unlink(self):
        for package in self.package_id:require_fruit_operation(self.env,package.step_tag_kind)
        return super().unlink()
