"""Document control extends the existing shipping documentation records."""
from datetime import timedelta
from odoo import api, fields, models, Command, _
from odoo.exceptions import ValidationError

KINDS = [('pf','Proforma'), ('ie','Instructivo de embarque'), ('pl','Packing List'),
         ('invoice','Invoice'), ('bl_nv','BL No Valorizado'), ('bl_v','BL Valorizado'),
         ('fx','Factura exportación'), ('other','Otro')]


def preserve_control_documents(records):
    if records:
        raise ValidationError(_('Migre y conserve estos documentos antes de retirar Control de exportación.'))


def deadline_color(due, actual, today):
    if not due:
        return 'unknown'
    comparison = actual or today
    return 'late' if comparison > due else 'today' if comparison == due else 'ontime'


class DocumentType(models.Model):
    _name = 'step.export.document.type'
    _description = 'Documento de exportación y plazo de envío'
    _order = 'sequence,id'
    name = fields.Char(required=True)
    code = fields.Char(string='Sigla', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    kind = fields.Selection(selection=lambda self: self.env['step.export.shipping.document']._fields['kind']._description_selection(self.env), required=True)
    customer_days = fields.Integer(string='Días desde zarpe para envío al cliente')
    customs_required = fields.Boolean(string='Controlar recepción de aduana')
    customs_days = fields.Integer(string='Días desde zarpe para recepción de aduana')
    _sql_constraints = [('code_unique','unique(code)','La sigla ya existe.'),
                        ('kind_unique','unique(kind)','Ya existe un parámetro para este tipo de documento.')]


class ShippingDocument(models.Model):
    _inherit = 'step.export.shipping.document'
    kind = fields.Selection(selection_add=KINDS, ondelete={key:preserve_control_documents for key,_label in KINDS})
    control_type_id = fields.Many2one('step.export.document.type', compute='_compute_control', string='Parámetro')
    customer_deadline = fields.Date(compute='_compute_control', string='Fecha máxima cliente')
    customs_deadline = fields.Date(compute='_compute_control', string='Fecha máxima aduana')
    document_created_on = fields.Date(string='Creación del documento')
    sent_on = fields.Date(string='Fecha real de envío', copy=False)
    received_on = fields.Date(string='Recepción de aduana', copy=False)
    manual_reference = fields.Char(string='Respaldo del registro manual', copy=False)
    sent_message_id = fields.Many2one('mail.message', string='Correo enviado', readonly=True, copy=False, ondelete='set null')
    sent_attachment_ids = fields.Many2many('ir.attachment', string='Adjuntos enviados', readonly=True, copy=False)
    effective_sent_on = fields.Date(compute='_compute_control', string='Fecha real')
    control_status = fields.Selection([('pending','P · Pendiente'),('sent','E · Enviado')],compute='_compute_control',string='Estado de envío')
    control_color = fields.Selection([('unknown','Sin fecha de zarpe'),('ontime','A tiempo'),('today','Fecha límite'),('late','Fuera de plazo')],compute='_compute_control',string='Plazo')

    @api.depends('kind','shipment_id.departure_date','sent_on','date','status')
    @api.depends_context('control_date','tz')
    def _compute_control(self):
        types = {t.kind:t for t in self.env['step.export.document.type'].with_context(active_test=False).search([])}
        today = fields.Date.to_date(self.env.context.get('control_date')) or fields.Date.context_today(self)
        for line in self:
            parameter = types.get(line.kind)
            etd = line.shipment_id.departure_date
            line.control_type_id = parameter
            line.customer_deadline = etd + timedelta(days=parameter.customer_days) if etd and parameter else False
            line.customs_deadline = etd + timedelta(days=parameter.customs_days) if etd and parameter and parameter.customs_required else False
            line.effective_sent_on = line.sent_on or (line.date if line.status == 'sent' else False)
            line.control_status = 'sent' if line.effective_sent_on else 'pending'
            line.control_color = deadline_color(line.customer_deadline,line.effective_sent_on,today)

    @api.constrains('sent_on','manual_reference','sent_message_id')
    def _check_manual_evidence(self):
        for line in self:
            if line.sent_on and not (line.sent_message_id or line.manual_reference):
                raise ValidationError(_('Indique el respaldo del envío manual o utilice el correo del sistema.'))


class Shipment(models.Model):
    _inherit = 'step.export.export'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.action_complete_document_control()
        return records

    def action_complete_document_control(self):
        self.check_access('write')
        if self:
            self.env.cr.execute('SELECT id FROM step_export_export WHERE id IN %s ORDER BY id FOR UPDATE',[tuple(sorted(self.ids))])
            self.invalidate_recordset(['documentation_ids'])
        parameters = self.env['step.export.document.type'].search([])
        for record in self:
            present = set(record.documentation_ids.mapped('kind'))
            record.write({'documentation_ids':[Command.create({'kind':t.kind,'sequence':t.sequence}) for t in parameters if t.kind not in present]})
        return True

    def action_prepare_control_email(self):
        self.ensure_one()
        return {'type':'ir.actions.act_window','res_model':'mail.compose.message','view_mode':'form','target':'new',
            'context':{'default_model':self._name,'default_res_ids':self.ids,'default_composition_mode':'comment',
                       'default_partner_ids':[Command.set(self.receiver_id.ids)],'force_email':True}}

    @api.model
    def control_dashboard(self, mode='documents', season_id=False, query='', consultation_date=False):
        if mode not in ('documents','vessels'):
            raise ValidationError(_('Panel desconocido.'))
        today = fields.Date.to_date(consultation_date) or fields.Date.context_today(self)
        domain = [('company_id','in',self.env.companies.ids)]
        if season_id:
            domain.append(('season_id','=',int(season_id)))
        if mode == 'vessels':
            domain.append(('transport_type','=','sea'))
        if query:
            domain += ['|','|',('shipment_number','ilike',query),('vessel_id.name','ilike',query),('container_reference','ilike',query)]
        total = self.search_count(domain)
        shipments = self.with_context(control_date=str(today)).search(domain,order='departure_date desc,id desc',limit=500)
        types = self.env['step.export.document.type'].search([])
        rows = []
        for s in shipments:
            row = {'id':s.id,'number':s.shipment_number or s.name,'container':s.container_reference or '',
                   'vessel':s.vessel_id.name or '', 'destination':s.destination_port_id.display_name or s.destination_port or '',
                   'etd':str(s.departure_date or ''),'eta':str(s.arrival_date or ''),'season':s.season_id.display_name or '',
                   'documents':[], **s._voyage_control_values(today)}
            for t in types:
                lines = s.documentation_ids.filtered(lambda l:l.kind==t.kind)
                # Never hide duplicate legacy rows behind a healthy summary.
                actual = min(lines.mapped('effective_sent_on')) if lines and all(lines.mapped('effective_sent_on')) else False
                due = s.departure_date + timedelta(days=t.customer_days) if s.departure_date else False
                row['documents'].append({'kind':t.kind,'sent':bool(actual),'date':str(actual or ''),
                    'deadline':str(due or ''),'color':deadline_color(due,actual,today),'duplicates':len(lines)>1})
            rows.append(row)
        seasons = self.env['step.temporada'].search_read([],['display_name'],order='id desc')
        heartbeat = self.env['ir.config_parameter'].sudo().get_param('step_export_control.ais_heartbeat')
        return {'rows':rows,'total':total,'date':str(today),'seasons':seasons,
                'types':[{'kind':t.kind,'code':t.code,'name':t.name,'days':t.customer_days} for t in types],
                'ais_heartbeat':heartbeat or False}
