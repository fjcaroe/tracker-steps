# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StepMobilizationInspectionTemplate(models.Model):
    """Plantilla versionada de checklist de inspección (base: Anexo 4,
    inspección visual + operacional). Los valores numéricos del formulario
    fuente (medidas, mm, cm) van en la etiqueta del ítem como texto de la
    versión, no como constraints de código."""
    _name = 'step.mobilization.inspection.template'
    _description = 'Plantilla de inspección de vehículo'
    _order = 'version desc'

    name = fields.Char(string='Nombre', required=True)
    version = fields.Integer(string='Versión', default=1, required=True)
    active = fields.Boolean(default=True)
    line_ids = fields.One2many('step.mobilization.inspection.template.line', 'template_id', string='Ítems')


class StepMobilizationInspectionTemplateLine(models.Model):
    _name = 'step.mobilization.inspection.template.line'
    _description = 'Ítem de checklist de inspección'
    _order = 'sequence, id'

    template_id = fields.Many2one('step.mobilization.inspection.template', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    category = fields.Selection(
        selection=[('visual', 'Inspección visual'), ('operational', 'Inspección operacional')],
        string='Categoría', required=True)
    label = fields.Char(string='Ítem', required=True)
    is_critical = fields.Boolean(string='Crítico', default=False,
                                  help='Un "No" en un ítem crítico bloquea la apertura de viajes con este '
                                       'vehículo hasta el cierre/autorización documentada.')


class StepMobilizationInspection(models.Model):
    _name = 'step.mobilization.inspection'
    _inherit = ['mail.thread']
    _description = 'Inspección de vehículo de movilización'
    _order = 'date desc'

    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                  default=lambda self: self.env.company)
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehículo', required=True)
    chofer_id = fields.Many2one('res.partner', string='Chofer', domain=[('step_chofer', '=', True)])
    inspector_id = fields.Many2one('res.users', string='Inspector', default=lambda self: self.env.user)
    date = fields.Datetime(string='Fecha/hora', required=True, default=fields.Datetime.now)
    odometer = fields.Float(string='Odómetro')
    location = fields.Char(string='Ubicación')
    template_id = fields.Many2one('step.mobilization.inspection.template', string='Plantilla', required=True)
    line_ids = fields.One2many('step.mobilization.inspection.line', 'inspection_id', string='Resultados')
    signature = fields.Binary(string='Firma', attachment=True)
    has_critical_failure = fields.Boolean(string='Tiene falla crítica', compute='_compute_has_critical_failure',
                                           store=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Borrador'),
            ('approved', 'Aprobado'),
            ('approved_observations', 'Aprobado con observaciones'),
            ('rejected', 'Rechazado'),
        ],
        string='Resultado', default='draft', required=True)

    @api.depends('line_ids.result', 'line_ids.is_critical')
    def _compute_has_critical_failure(self):
        for record in self:
            record.has_critical_failure = any(
                line.result == 'no' and line.is_critical for line in record.line_ids)

    @api.onchange('template_id')
    def _onchange_template_id(self):
        if self.template_id:
            self.line_ids = [(5, 0, 0)] + [(0, 0, {
                'template_line_id': line.id,
                'category': line.category,
                'label': line.label,
                'is_critical': line.is_critical,
            }) for line in self.template_id.line_ids]

    def action_close(self):
        for record in self:
            if not record.line_ids:
                raise UserError(_('La inspección no tiene ítems evaluados.'))
            if record.has_critical_failure:
                record.state = 'rejected'
            elif any(line.result == 'no' for line in record.line_ids):
                record.state = 'approved_observations'
            else:
                record.state = 'approved'


class StepMobilizationInspectionLine(models.Model):
    _name = 'step.mobilization.inspection.line'
    _description = 'Resultado de ítem de inspección'

    inspection_id = fields.Many2one('step.mobilization.inspection', required=True, ondelete='cascade')
    template_line_id = fields.Many2one('step.mobilization.inspection.template.line', string='Ítem de plantilla')
    category = fields.Selection(
        selection=[('visual', 'Inspección visual'), ('operational', 'Inspección operacional')], string='Categoría')
    label = fields.Char(string='Ítem', required=True)
    result = fields.Selection(
        selection=[('si', 'Sí'), ('no', 'No'), ('na', 'No aplica')], string='Resultado', required=True)
    observation = fields.Char(string='Observación')
    evidence = fields.Binary(string='Evidencia fotográfica', attachment=True)
    is_critical = fields.Boolean(string='Crítico')
