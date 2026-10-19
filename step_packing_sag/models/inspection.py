"""Internal preparation and transcription of an externally issued SAG decision.

Reference: Programa Origen, Manual para Externos v04, 10 July 2024,
sections 6.3, 6.4, 6.5 and 6.10. No scheduling or certification API.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

CHECKS = ('sag_initial', 'sag_documents', 'sag_traceability', 'sag_presentation', 'sag_packaging')
CHECK = [('pending', 'Por verificar'), ('yes', 'Conforme'), ('no', 'No conforme')]


class Inspection(models.Model):
    _inherit = 'step.packing.inspection'

    # False on historical rows: installation must not rewrite approved results.
    sag_prototype = fields.Boolean('Prototipo SAG', default=False, copy=False, readonly=True)
    sag_phase = fields.Selection([
        ('preparing', 'Preparación'), ('ready', 'Lista para solicitar'),
        ('requested', 'Servicio solicitado'), ('pending', 'Pendiente de laboratorio'),
    ], string='Seguimiento interno', default='preparing', copy=False)
    sag_status = fields.Char('Seguimiento', compute='_compute_sag_status')
    sag_country_id = fields.Many2one('res.country', string='País de destino')
    sag_counterpart_id = fields.Many2one('res.partner', string='Contraparte del establecimiento', check_company=True)
    sag_packing_id = fields.Many2one(related='production_id.packing_partner_id', string='Packing')
    sag_species_id = fields.Many2one(related='production_id.fruit_species_id', string='Especie')
    sag_grower_id = fields.Many2one(related='production_id.fruit_grower_id', string='Productor de la OT')
    sag_requirements = fields.Text('Requisitos por país / protocolo y fecha de consulta')
    sag_request_reference = fields.Char('Nº solicitud de servicio externa', copy=False)
    sag_scheduled_at = fields.Datetime('Horario asignado por SAG', copy=False)
    sag_sif_reference = fields.Char('Nº SIF / libro foliado', copy=False)
    sag_initial = fields.Selection(CHECK, string='Contraparte, sala y equipamiento (6.4.1)', default='pending')
    sag_documents = fields.Selection(CHECK, string='SIF, detalle de lote y documentos aplicables (6.4.2)', default='pending')
    sag_traceability = fields.Selection(CHECK, string='Registros, habilitación y exclusiones CSG/CSP/SdP (6.4.2)', default='pending')
    sag_presentation = fields.Selection(CHECK, string='Identificación, separación y resguardo del lote (6.4.4)', default='pending')
    sag_packaging = fields.Selection(CHECK, string='Envases, rotulado y madera cuando aplique (6.4.4)', default='pending')
    sag_sampling_basis = fields.Text('Criterio y nivel de muestreo aplicado (Anexo 7)')
    sag_sample_count = fields.Integer('Unidades de muestreo inspeccionadas')
    sag_sample_findings = fields.Text('Tarjas muestreadas, plagas, pudrición, contaminantes y productores asociados')
    sag_laboratory_reference = fields.Char('Identificación de muestra / SISVEG / informe de laboratorio', copy=False)
    sag_laboratory_received = fields.Boolean('Resultado de laboratorio recibido y comunicado por SAG', copy=False)
    sag_treatment = fields.Selection([
        ('undetermined', 'Por determinar según mercado'), ('none', 'No corresponde según requisito consultado'),
        ('required', 'Requerido, pendiente'), ('done', 'Realizado, con respaldo'),
    ], string='Tratamiento cuarentenario / mitigación', default='undetermined')
    sag_treatment_detail = fields.Text('Tipo, número, fecha y condiciones del tratamiento / resguardo')
    sag_evidence_ids = fields.Many2many('ir.attachment', relation='step_packing_sag_evidence_rel',
        string='Respaldos SIF, PFI, protocolos, tratamiento e informe', copy=False)

    @api.depends('state', 'sag_phase')
    def _compute_sag_status(self):
        phases = dict(self._fields['sag_phase'].selection)
        for rec in self:
            rec.sag_status = {'approved': 'Aprobación externa registrada', 'rejected': 'Rechazo externo registrado'}.get(rec.state, phases.get(rec.sag_phase))

    @api.model_create_multi
    def create(self, vals_list):
        defaults = self.default_get(['kind'])
        for vals in vals_list:
            vals['sag_prototype'] = vals.get('kind', defaults.get('kind')) == 'sag'
        return super().create(vals_list)

    def write(self, vals):
        if 'sag_prototype' in vals:
            raise UserError(_('No se modifica la identificación del prototipo ni el histórico.'))
        if 'kind' in vals and any(vals['kind'] != r.kind for r in self):
            raise UserError(_('Cree otra inspección para un tipo distinto.'))
        return super().write(vals)

    @api.constrains('sag_sample_count', 'sag_evidence_ids')
    def _check_sag_data(self):
        for rec in self:
            if rec.sag_sample_count < 0:
                raise ValidationError(_('La cantidad de muestra no puede ser negativa.'))
            if any(a.res_model != rec._name or a.res_id != rec.id for a in rec.sag_evidence_ids):
                raise ValidationError(_('Adjunte respaldos propios de esta inspección.'))

    def _sag_ready(self):
        self.check_access('write')
        self.production_id._lock_process()
        if self:
            self.env.cr.execute('SELECT id FROM step_packing_inspection WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(sorted(self.ids))])
            self.invalidate_recordset()
        for rec in self:
            if rec.kind != 'sag' or not rec.sag_prototype or rec.state != 'draft':
                raise UserError(_('Seleccione una inspección SAG del prototipo en borrador.'))
            if not rec.sag_country_id or not rec.sag_counterpart_id or not (rec.sag_requirements or '').strip():
                raise UserError(_('Indique país, contraparte y requisitos consultados con su fecha.'))
            if any(rec[name] != 'yes' for name in CHECKS):
                raise UserError(_('Complete los cinco controles de preparación como conformes.'))
            if rec.sag_treatment in (False, 'undetermined', 'required'):
                raise UserError(_('Resuelva el tratamiento requerido según mercado.'))
            if rec.sag_treatment == 'done' and not (rec.sag_treatment_detail or '').strip():
                raise UserError(_('Registre tipo, número, fecha y condiciones del tratamiento.'))
        return True

    def action_sag_ready(self):
        self._sag_ready()
        return self.write({'sag_phase': 'ready'})

    def action_sag_requested(self):
        self._sag_ready()
        for rec in self:
            if not (rec.sag_request_reference or '').strip() or not rec.sag_scheduled_at:
                raise UserError(_('Registre la solicitud externa y el horario asignado por SAG.'))
        return self.write({'sag_phase': 'requested'})

    def action_sag_pending(self):
        self._sag_ready()
        for rec in self:
            if not (rec.sag_laboratory_reference or '').strip() or not (rec.observations or '').strip():
                raise UserError(_('Identifique la muestra de laboratorio y el motivo pendiente.'))
        return self.write({'sag_phase': 'pending', 'sag_laboratory_received': False})

    def _review(self, approved):
        # Revalidate substantive fields at the final operation: RPC or editing a
        # phase alone cannot manufacture a SAG decision or bypass the checklist.
        self.check_access('write')
        self.production_id._lock_process()
        if self:
            self.env.cr.execute('SELECT id FROM step_packing_inspection WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(sorted(self.ids))])
            self.invalidate_recordset()
        for rec in self.filtered(lambda r: r.kind == 'sag' and r.sag_prototype):
            if not rec.sag_country_id or not (rec.sag_sif_reference or '').strip() or not rec.sag_evidence_ids:
                raise UserError(_('Indique el país y la SIF, y adjunte el respaldo del resultado externo.'))
            rec._check_sag_data()
            if approved:
                rec._sag_ready()
                if rec.sag_phase == 'pending' and (not rec.sag_laboratory_received or not (rec.sag_laboratory_reference or '').strip()):
                    raise UserError(_('Identifique el informe de laboratorio comunicado por SAG.'))
                if not (rec.sag_request_reference or '').strip() or not rec.sag_scheduled_at:
                    raise UserError(_('Registre la solicitud externa y su horario.'))
                if rec.sag_sample_count <= 0 or not (rec.sag_sampling_basis or '').strip() or not (rec.sag_sample_findings or '').strip():
                    raise UserError(_('Registre nivel, cantidad y hallazgos de la muestra inspeccionada.'))
        return super()._review(approved)


class Shipment(models.Model):
    _inherit = 'step.export.export'

    def _check_tag_load(self):
        result = super()._check_tag_load()
        for shipment in self:
            records = self.env['step.packing.inspection'].search([
                ('sag_prototype', '=', True), ('kind', '=', 'sag'),
                ('package_ids', 'in', shipment.tag_ids.ids),
            ], order='id desc')
            for tag in shipment.tag_ids:
                applicable = records.filtered(lambda r: tag in r.package_ids and r.sag_country_id == shipment.destination_country_id)
                # A pending reevaluation must not inherit an older approval.
                latest = applicable[:1]
                if latest and latest.state != 'approved':
                    raise UserError(_('La tarja %s tiene una inspección SAG pendiente o rechazada para el destino.') % tag.name)
                foreign = records.filtered(lambda r: tag in r.package_ids)
                if foreign and not latest:
                    raise UserError(_('La inspección SAG de %s no acredita el país del despacho.') % tag.name)
        return result
