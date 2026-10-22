from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


# Stable native relations; no names, copied masters or cross-company sudo.
ACTIVITIES = {
    'cost': ('Costos', 'step.tarja.cost.line', 'cost_id_domain'),
    'forecast': ('Pronóstico cosecha', 'step.agriculture.harvest.forecast', 'cost_center_id'),
    'machinery': ('Maquinaria', 'step.hrs.machinery.line', 'cost_id'),
    'movement': ('Movilización', 'step.movi.cost.line', 'cost_id'),
    'harvest': ('Cosecha', 'step.agriculture.harvest.record', 'cost_center_id'),
    'irrigation': ('Riego', 'step.agriculture.irrigation.valve', 'cost_center_id'),
    'contractor': ('Contratistas', 'step.tarja.cost.line', 'cost_id'),
    'own': ('Tarja propia', 'step.tarja.line', 'cost_id'),
    'foliar': ('Aplicación foliar', 'step.agriculture.application.machinery', 'cost_center_id'),
    'monitoring': ('Monitoreo', 'step.agriculture.monitoring.line', 'cost_center_id'),
    'advisory': ('Asesoría', 'step.agriculture.advisory', 'cost_center_id'),
    'inspection': ('Inspecciones', 'step.agriculture.inspection', 'cost_center_id'),
}


class CostCenter(models.Model):
    _inherit = 'account.analytic.account'

    agriculture_sector_id = fields.Many2one('step.agriculture.irrigation.sector', string='Sector de riego')
    agriculture_valve_id = fields.Many2one('step.agriculture.irrigation.valve', string='Válvula')
    agriculture_cost_count = fields.Integer(compute='_compute_agriculture_activity')
    agriculture_forecast_count = fields.Integer(compute='_compute_agriculture_activity')
    agriculture_machinery_count = fields.Integer(compute='_compute_agriculture_activity')
    agriculture_movement_count = fields.Integer(compute='_compute_agriculture_activity')
    agriculture_harvest_count = fields.Integer(compute='_compute_agriculture_activity')
    agriculture_irrigation_count = fields.Integer(compute='_compute_agriculture_activity')
    agriculture_contractor_count = fields.Integer(compute='_compute_agriculture_activity')
    agriculture_own_count = fields.Integer(compute='_compute_agriculture_activity')
    agriculture_foliar_count = fields.Integer(compute='_compute_agriculture_activity')
    agriculture_monitoring_count = fields.Integer(compute='_compute_agriculture_activity')
    agriculture_advisory_count = fields.Integer(compute='_compute_agriculture_activity')
    agriculture_inspection_count = fields.Integer(compute='_compute_agriculture_activity')
    agriculture_can_cost = fields.Boolean(compute='_compute_agriculture_activity')
    agriculture_can_forecast = fields.Boolean(compute='_compute_agriculture_activity')
    agriculture_can_machinery = fields.Boolean(compute='_compute_agriculture_activity')
    agriculture_can_movement = fields.Boolean(compute='_compute_agriculture_activity')
    agriculture_can_harvest = fields.Boolean(compute='_compute_agriculture_activity')
    agriculture_can_irrigation = fields.Boolean(compute='_compute_agriculture_activity')
    agriculture_can_contractor = fields.Boolean(compute='_compute_agriculture_activity')
    agriculture_can_own = fields.Boolean(compute='_compute_agriculture_activity')
    agriculture_can_foliar = fields.Boolean(compute='_compute_agriculture_activity')
    agriculture_can_monitoring = fields.Boolean(compute='_compute_agriculture_activity')
    agriculture_can_advisory = fields.Boolean(compute='_compute_agriculture_activity')
    agriculture_can_inspection = fields.Boolean(compute='_compute_agriculture_activity')

    @api.depends_context('uid', 'allowed_company_ids')
    def _compute_agriculture_activity(self):
        for key, (label, model_name, relation) in ACTIVITIES.items():
            model = self.env[model_name]
            allowed = model.has_access('read')
            for center in self:
                center['agriculture_can_' + key] = allowed
                center['agriculture_' + key + '_count'] = (
                    model.search_count([(relation, '=', center.id)]) if allowed and center.id else 0)

    def action_agriculture_activity(self):
        self.ensure_one()
        self.check_access('read')
        key = self.env.context.get('agriculture_activity')
        if key not in ACTIVITIES:
            raise UserError(_('Seleccione una actividad agrícola válida.'))
        label, model_name, relation = ACTIVITIES[key]
        if key == 'monitoring' and self.env.context.get('agriculture_pest_view'):
            label = _('Plaga')
        model = self.env[model_name]
        if not model.has_access('read'):
            raise AccessError(_('No tiene permiso para consultar esta actividad.'))
        default = [self.id] if model._fields[relation].type == 'many2many' else self.id
        # The cost-center directory is read-only. Its view flags and defaults
        # must not disable the related document's own permitted workflow.
        inherited = {'create', 'edit', 'delete', 'active_id', 'active_ids', 'active_model',
                     'form_view_ref', 'list_view_ref', 'tree_view_ref', 'search_view_ref', 'group_by'}
        context = {key: value for key, value in self.env.context.items()
                   if key not in inherited and not key.startswith(('default_', 'search_default_'))}
        context['default_' + relation] = default
        # Odoo's object-button dispatcher merges the parent context again
        # after this method returns. Override those flags explicitly using
        # the destination ACLs; omitting them leaves the directory read-only.
        context.update(create=model.has_access('create'), edit=model.has_access('write'),
                       delete=model.has_access('unlink'))
        action = {'type': 'ir.actions.act_window', 'name': label, 'res_model': model_name,
                  'view_mode': 'list,form', 'domain': [(relation, '=', self.id)],
                  'context': context}
        if model_name.startswith('step.agriculture.'):
            suffix = model_name.removeprefix('step.agriculture.').replace('.', '_')
            action['views'] = [
                (self.env.ref('step_agriculture_records.view_' + suffix + '_' + kind).id, kind)
                for kind in ('list', 'form')]
        return action


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    agriculture_active_ingredient_id = fields.Many2one(
        'step.agriculture.active.ingredient', string='Sustancia activa')
    agriculture_max_withholding_days = fields.Integer(string='Días de carencia mayor')
    agriculture_eu_withholding_days = fields.Integer(string='Días de carencia UE')
    agriculture_us_withholding_days = fields.Integer(string='Días de carencia USA')
    agriculture_max_applications = fields.Integer(string='Máximo de aplicaciones')
    # Unclassified non-labor products already exist. Do not invent a labor
    # classification for them merely to add the substance relation.
    grupo_labor = fields.Selection(required=False)

