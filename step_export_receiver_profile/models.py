from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class Partner(models.Model):
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


class Shipment(models.Model):
    _inherit = 'step.export.export'

    eligible_receiver_ids = fields.Many2many('res.partner', compute='_compute_eligible_receivers')
    receiver_id = fields.Many2one(domain="[('id','in',eligible_receiver_ids)]")

    @api.model_create_multi
    def create(self, vals_list):
        values = []
        for vals in vals_list:
            vals = dict(vals)
            if vals.get('receiver_id'):
                receiver = self.env['res.partner'].browse(vals['receiver_id'])
                receiver.check_access('read')
                vals.setdefault('notify_id', receiver.step_export_default_notify_id.id)
                vals.setdefault('consignee_id', receiver.step_export_default_consignee_id.id)
            values.append(vals)
        return super().create(values)

    def write(self, vals):
        vals = dict(vals)
        if 'receiver_id' in vals:
            receiver = self.env['res.partner'].browse(vals['receiver_id'])
            receiver.check_access('read')
            vals.setdefault('notify_id', receiver.step_export_default_notify_id.id)
            vals.setdefault('consignee_id', receiver.step_export_default_consignee_id.id)
        return super().write(vals)

    @api.onchange('sales_program_id')
    def _onchange_sales_program_instruction(self):
        super()._onchange_sales_program_instruction()
        self._onchange_receiver_profile()

    @api.depends('sales_program_id.partner_id', 'sales_program_id.partner_id.step_export_generic_receiver',
                 'sales_program_id.partner_id.step_export_market_id')
    def _compute_eligible_receivers(self):
        for shipment in self:
            source = shipment.sales_program_id.partner_id
            shipment.eligible_receiver_ids = (self.env['res.partner'].search([
                ('step_export_receiver', '=', True), ('step_export_generic_receiver', '=', False),
                ('step_export_market_id', '=', source.step_export_market_id.id)]) | source
                if source.step_export_generic_receiver and source.step_export_market_id else source)

    @api.onchange('receiver_id')
    def _onchange_receiver_profile(self):
        for shipment in self:
            shipment.notify_id = shipment.receiver_id.step_export_default_notify_id
            shipment.consignee_id = shipment.receiver_id.step_export_default_consignee_id

    def _check_program_receiver(self):
        for shipment in self:
            source, receiver = shipment.sales_program_id.partner_id, shipment.receiver_id
            if source and receiver and source != receiver:
                receiver.check_access('read')
                if not (source.step_export_generic_receiver and source.step_export_market_id
                        and source.step_export_market_id == receiver.step_export_market_id
                        and receiver.step_export_receiver and not receiver.step_export_generic_receiver):
                    raise ValidationError(_('El recibidor debe ser el del programa o un recibidor del mismo mercado de su programa genérico.'))

    @api.constrains('sales_program_id', 'receiver_id')
    def _check_receiver_market(self):
        self._check_program_receiver()

    def action_validate_shipment(self):
        # Preserve the native transition and checks, with the explicitly selected
        # receiver for generic programmes. No programme or historic recipient is changed.
        ordinary = self.filtered(lambda shipment: not shipment.sales_program_id.partner_id.step_export_generic_receiver)
        result = super(Shipment, ordinary).action_validate_shipment() if ordinary else True
        for shipment in self - ordinary:
            if shipment.state != 'draft' or not shipment.sales_program_id or not shipment.line_ids:
                raise UserError(_('Indique programa y carga antes de validar el instructivo.'))
            if shipment.sales_program_id.state != 'current':
                raise UserError(_('El programa de ventas debe estar vigente.'))
            shipment._check_program_receiver()
            if not shipment.receiver_id or shipment.receiver_id.step_export_generic_receiver:
                raise ValidationError(_('Seleccione el recibidor definitivo del mismo mercado.'))
            shipment.write({'state': 'validated', 'season_id': shipment.sales_program_id.season_id.id,
                            'species_id': shipment.sales_program_id.species_id.id})
        return result
