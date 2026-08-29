# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class StepMobilizationDocumentType(models.Model):
    _name = 'step.mobilization.document.type'
    _description = 'Tipo de documento de cumplimiento de Movilización'

    name = fields.Char(string='Nombre', required=True)
    scope = fields.Selection(
        selection=[
            ('transportista', 'Transportista'),
            ('chofer', 'Chofer'),
            ('vehiculo', 'Vehículo'),
            ('contrato', 'Contrato'),
        ],
        string='Alcance', required=True)
    is_blocking = fields.Boolean(string='Bloqueante', default=True,
                                  help='Si está vencido/faltante, bloquea abrir un viaje para el '
                                       'transportista/chofer/vehículo asociado.')
    reminder_days = fields.Integer(string='Aviso previo al vencimiento (días)', default=30)
    active = fields.Boolean(default=True)


class StepMobilizationDocument(models.Model):
    _name = 'step.mobilization.document'
    _inherit = ['mail.thread']
    _description = 'Documento de cumplimiento de Movilización'
    _order = 'expiry_date'

    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                  default=lambda self: self.env.company)
    type_id = fields.Many2one('step.mobilization.document.type', string='Tipo de documento', required=True)
    scope = fields.Selection(related='type_id.scope', string='Alcance', store=True)
    transporter_id = fields.Many2one('res.partner', string='Transportista',
                                      domain=[('step_trans_person', '=', True)])
    chofer_id = fields.Many2one('res.partner', string='Chofer', domain=[('step_chofer', '=', True)])
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo')
    contract_id = fields.Many2one('step.mobilization.contract', string='Contrato')
    issue_date = fields.Date(string='Fecha de emisión')
    expiry_date = fields.Date(string='Fecha de vencimiento')
    attachment = fields.Binary(string='Documento', attachment=True)
    attachment_filename = fields.Char()
    review_state = fields.Selection(
        selection=[('pending', 'Pendiente'), ('approved', 'Aprobado'), ('rejected', 'Rechazado')],
        default='pending', required=True, string='Estado de revisión')
    observations = fields.Text(string='Observaciones')
    responsible_id = fields.Many2one('res.users', string='Responsable', default=lambda self: self.env.user)

    @api.constrains('scope', 'transporter_id', 'chofer_id', 'vehicle_id', 'contract_id')
    def _check_scope_target(self):
        for record in self:
            target = {'transportista': record.transporter_id, 'chofer': record.chofer_id,
                      'vehiculo': record.vehicle_id, 'contrato': record.contract_id}.get(record.scope)
            if not target:
                raise ValidationError(_('Debe indicar el %s al que corresponde este documento.') % record.scope)
