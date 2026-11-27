from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


ROLES = {'carrier_id': 'step_export_carrier', 'consignee_id': 'step_export_consignee',
         'notify_id': 'step_export_notify', 'freight_forwarder_id': 'step_export_forwarder',
         'customs_agent_id': 'step_export_customs_agent'}


class Market(models.Model):
    _name = 'step.fruit.market'
    _description = 'Mercado de fruta'
    _order = 'code, name'

    code = fields.Char(string='Código', required=True, index=True)
    name = fields.Char(string='Nombre', required=True)
    abbreviation = fields.Char(string='Abreviatura', required=True)
    active = fields.Boolean(default=True)
    _sql_constraints = [('market_code_unique', 'unique(code)', 'El código de mercado ya existe.')]


class ResPartner(models.Model):
    _inherit = "res.partner"

    step_export_receiver = fields.Boolean(string="Recibidor")


class ExportPartnerRoles(models.Model):
    _inherit = 'res.partner'
    step_export_carrier = fields.Boolean(string='Naviera o aerolínea')
    step_export_consignee = fields.Boolean(string='Consignatario')
    step_export_notify = fields.Boolean(string='Notify')
    step_export_forwarder = fields.Boolean(string='Agencia de carga')
    step_export_customs_agent = fields.Boolean(string='Agente de aduana')

    @api.onchange(*ROLES.values())
    def _onchange_export_roles(self):
        for partner in self:
            if any(partner[name] for name in ROLES.values()):
                partner.step_export = True

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if any(vals.get(name) for name in ROLES.values()):
                vals['step_export'] = True
        return super().create(vals_list)

    def write(self, vals):
        if any(vals.get(name) for name in ROLES.values()):
            vals = dict(vals, step_export=True)
        return super().write(vals)


class ReceiverProfile(models.Model):
    _inherit = 'res.partner'

    step_export_market_id = fields.Many2one('step.fruit.market', string='Mercado', ondelete='restrict')
    step_export_generic_receiver = fields.Boolean(string='Recibidor genérico')
    step_export_default_notify_id = fields.Many2one('res.partner', string='Notify del recibidor',
        domain=[('step_export_notify', '=', True)], ondelete='restrict')
    step_export_default_consignee_id = fields.Many2one('res.partner', string='Consignatario del recibidor',
        domain=[('step_export_consignee', '=', True)], ondelete='restrict')

    @api.constrains('step_export_generic_receiver', 'step_export_market_id',
                    'step_export_default_notify_id', 'step_export_default_consignee_id')
    def _check_receiver_profile(self):
        for partner in self:
            if partner.step_export_generic_receiver and not partner.step_export_market_id:
                raise ValidationError(_('Un recibidor genérico requiere mercado.'))
            for field, role in [('step_export_default_notify_id', 'step_export_notify'),
                                ('step_export_default_consignee_id', 'step_export_consignee')]:
                contact = partner[field]
                if contact:
                    contact.check_access('read')
                    if not contact[role]:
                        raise ValidationError(_('El contacto debe tener marcado el rol correspondiente de Exportación.'))
