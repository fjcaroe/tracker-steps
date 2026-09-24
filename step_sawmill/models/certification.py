# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class StepSawmillCertification(models.Model):
    _name = 'step.sawmill.certification'
    _description = 'Certificación de impregnado'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sent_date desc, id desc'

    name = fields.Char(string='Descripción', required=True, tracking=True)
    state = fields.Selection(
        [('sent', 'Enviada'), ('certified', 'Certificada')],
        string='Estado', default='sent', required=True, copy=False, tracking=True)
    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                 default=lambda self: self.env.company)
    work_order_id = fields.Many2one('step.sawmill.work.order', string='Orden de trabajo')
    impregnation_id = fields.Many2one('step.sawmill.impregnation', string='Impregnado')
    load_sheet = fields.Char(string='Hoja de carga')
    sample = fields.Char(string='Muestra')
    laboratory_id = fields.Many2one('res.partner', string='Laboratorio')
    sent_date = fields.Datetime(string='Fecha envío')
    certification_date = fields.Date(string='Fecha certificación')
    retention_result = fields.Float(string='Resultado retención')
    penetration = fields.Float(string='Penetración')
    line_ids = fields.One2many('step.sawmill.certification.line', 'certification_id',
                               string='Detalle')

    def action_certify(self):
        if any(rec.state != 'sent' for rec in self):
            raise UserError(_('Solo se puede certificar una solicitud Enviada.'))
        self.write({
            'state': 'certified',
            'certification_date': self.env.context.get('certification_date')
            or fields.Date.context_today(self),
        })

    def action_reset(self):
        self.write({'state': 'sent'})


class StepSawmillCertificationLine(models.Model):
    _name = 'step.sawmill.certification.line'
    _description = 'Línea de certificación'
    _order = 'sequence, id'

    certification_id = fields.Many2one('step.sawmill.certification', required=True,
                                       ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Línea')
    load_sheet = fields.Char(string='Hoja de carga')
    preservative = fields.Char(string='Preservante')
    impregnation_date = fields.Date(string='Fecha impregnación')
    product_category = fields.Char(string='Categoría productos')
    product_id = fields.Many2one('product.product', string='Producto')
    thickness = fields.Float(string='Espesor')
    width = fields.Float(string='Ancho')
    length = fields.Float(string='Largo')
    pieces = fields.Integer(string='Cantidad piezas')
    quantity_inches = fields.Float(string='Pulgadas')
    m3_theoretical = fields.Float(string='m³ teóricos')
    m3_real = fields.Float(string='m³ reales')
