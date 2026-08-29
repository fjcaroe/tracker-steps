# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import UserError


class StepMobilizationRightToKnowTemplate(models.Model):
    """Plantilla versionada de la matriz actividad-riesgo-consecuencia-medidas
    (Derecho a Saber, Art. 21 DS 40). Contenido administrable: las filas
    iniciales del Anexo 2 se cargan como datos de ejemplo editables, no como
    texto fijo en código."""
    _name = 'step.mobilization.right_to_know.template'
    _description = 'Plantilla de Derecho a Saber'
    _order = 'version desc'

    name = fields.Char(string='Nombre', required=True)
    version = fields.Integer(string='Versión', default=1, required=True)
    active = fields.Boolean(default=True)
    line_ids = fields.One2many('step.mobilization.right_to_know.template.line', 'template_id', string='Matriz')
    is_validated = fields.Boolean(string='Revisada por prevención de riesgos', default=False)

    def action_validate(self):
        self.write({'is_validated': True})


class StepMobilizationRightToKnowTemplateLine(models.Model):
    _name = 'step.mobilization.right_to_know.template.line'
    _description = 'Fila de matriz de riesgo (Derecho a Saber)'

    template_id = fields.Many2one('step.mobilization.right_to_know.template', required=True, ondelete='cascade')
    activity = fields.Char(string='Actividad', required=True)
    risk = fields.Char(string='Riesgo', required=True)
    consequence = fields.Char(string='Consecuencia', required=True)
    preventive_measure = fields.Text(string='Medidas preventivas', required=True)


class StepMobilizationRightToKnow(models.Model):
    _name = 'step.mobilization.right_to_know'
    _inherit = ['mail.thread']
    _description = 'Registro de Derecho a Saber de chofer'
    _order = 'date desc'

    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                  default=lambda self: self.env.company)
    transporter_id = fields.Many2one('res.partner', string='Empresa transportista', required=True,
                                      domain=[('step_trans_person', '=', True)])
    chofer_id = fields.Many2one('res.partner', string='Chofer', required=True,
                                 domain=[('step_chofer', '=', True)])
    position = fields.Char(string='Puesto de trabajo')
    date = fields.Date(string='Fecha', required=True, default=fields.Date.context_today)
    place = fields.Char(string='Lugar')
    relator_name = fields.Char(string='Relator')
    template_id = fields.Many2one('step.mobilization.right_to_know.template', string='Versión de plantilla',
                                   required=True)
    acceptance_evidence = fields.Binary(string='Evidencia de firma/aceptación', attachment=True)
    acceptance_evidence_filename = fields.Char()
    pdf_document = fields.Binary(string='PDF emitido', attachment=True, readonly=True, copy=False)
    pdf_document_filename = fields.Char()
    state = fields.Selection(
        selection=[('draft', 'Borrador'), ('issued', 'Emitido'), ('expired', 'Vencido')],
        default='draft', required=True, string='Estado')
    expiry_date = fields.Date(string='Vencimiento/renovación')

    def action_issue(self):
        for record in self:
            if not record.template_id.is_validated:
                raise UserError(_('La plantilla de Derecho a Saber "%s" no ha sido validada.')
                                 % record.template_id.name)
            if record.state != 'draft':
                raise UserError(_('Sólo un registro en borrador puede emitirse.'))
            record.write({'state': 'issued'})
