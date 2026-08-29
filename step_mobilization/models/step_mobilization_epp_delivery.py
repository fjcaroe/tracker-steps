# -*- coding: utf-8 -*-

from odoo import fields, models


class StepMobilizationEppDelivery(models.Model):
    _name = 'step.mobilization.epp.delivery'
    _inherit = ['mail.thread']
    _description = 'Entrega de EPP a chofer'
    _order = 'date desc'

    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                  default=lambda self: self.env.company)
    transporter_id = fields.Many2one('res.partner', string='Empresa transportista', required=True,
                                      domain=[('step_trans_person', '=', True)])
    chofer_id = fields.Many2one('res.partner', string='Chofer', required=True,
                                 domain=[('step_chofer', '=', True)])
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    delivered_by_id = fields.Many2one('res.users', string='Entregado por', default=lambda self: self.env.user)
    received_evidence = fields.Binary(string='Firma/evidencia de recepción', attachment=True)
    received_evidence_filename = fields.Char()
    line_ids = fields.One2many('step.mobilization.epp.delivery.line', 'delivery_id', string='Ítems entregados')
    state = fields.Selection(
        selection=[('draft', 'Borrador'), ('delivered', 'Entregado')],
        default='draft', required=True, string='Estado')

    def action_confirm(self):
        self.write({'state': 'delivered'})


class StepMobilizationEppDeliveryLine(models.Model):
    _name = 'step.mobilization.epp.delivery.line'
    _description = 'Ítem de EPP entregado'

    delivery_id = fields.Many2one('step.mobilization.epp.delivery', required=True, ondelete='cascade')
    item_name = fields.Char(string='Ítem', required=True,
                             help='Ej: chaleco/peto reflectante, gorro, bloqueador solar, manguillas, '
                                  'calzado de seguridad. Lista abierta, no exhaustiva.')
    quantity = fields.Integer(string='Cantidad', default=1)
    size = fields.Char(string='Talla')
    certification = fields.Char(string='Certificación')
    is_replacement = fields.Boolean(string='Es reposición')
    replacement_reason = fields.Char(string='Motivo de reposición')
