from odoo import api, fields, models, Command, _
from odoo.exceptions import UserError, ValidationError
import unicodedata

PAYMENT = [('collect', 'Collect'), ('prepaid', 'Prepaid')]
DOCUMENTS = [('dus', 'D.U.S. 2do envío'), ('bl', 'Conocimiento de embarque'),
             ('phyto', 'Certificado fitosanitario'), ('origin', 'Certificado de origen'), ('bill', 'Bill of Lading')]
DOCUMENT_REQUIREMENTS = [('dus',5,0,''), ('bl',3,8,''), ('phyto',1,3,''), ('origin',1,3,''),
    ('bill',0,0,'SWB emisión en origen. Cambio a SWB emisión en destino con previa confirmación shipper.')]
FREIGHT_CONCEPTS = (
    ('Documentación FEE - Destination', ('Documentation FEE - Destination',)),
    ('Gastos de importación', ()), ('Tasas portuarias en destino', ()), ('THC', ()),
    ('Flete marítimo', ()),
    ('Documentación FEE - Origen incluido Agente de Aduana', ('Documentation FEE - Origen incluido Agente de Aduana',)),
    ('Inland en origen', ()), ('Servicio AC (Atmósfera Controlada)', ('Servicio de AC (Atmósfera Controlada)',)),
    ('Late gate service - export', ()), ('Gate out', ()), ('Emisión BL', ()),
    ('Security fee', ()), ('Sistema de monitoreo', ()),
)


def _concept_key(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value or '').casefold()
                   if c.isalnum() and not unicodedata.combining(c))


class Company(models.Model):
    _inherit = 'res.company'
    export_folio_mode = fields.Selection([('document', 'Folios por documento'), ('shared', 'Folio comercial único')],
        string='Folios de exportación', default='document')
    export_folio_initial = fields.Integer(string='Número inicial', default=1)

    @api.constrains('export_folio_mode', 'export_folio_initial')
    def _check_initial(self):
        for company in self:
            if company.export_folio_mode == 'shared' and company.export_folio_initial <= 0:
                raise ValidationError(_('El número inicial debe ser positivo.'))


class Settings(models.TransientModel):
    _inherit = 'res.config.settings'
    export_folio_mode = fields.Selection(related='company_id.export_folio_mode', readonly=False)
    export_folio_initial = fields.Integer(related='company_id.export_folio_initial', readonly=False)


class Order(models.Model):
    _inherit = 'sale.order'
    export_folio = fields.Integer(string='Folio comercial único', copy=False,
        help='Ingreso manual desde el número inicial configurado. Se usa en Nota de venta, Proforma e Invoice comerciales e instructivo y embarque vinculados.')
    export_folio_mode = fields.Selection(related='company_id.export_folio_mode')
    export_document_number = fields.Char(compute='_compute_document_number', string='Número comercial')

    def init(self):
        # Ordinary orders have 0/NULL: only explicitly assigned positive folios
        # participate in the uniqueness rule.
        self.env.cr.execute('CREATE UNIQUE INDEX IF NOT EXISTS sale_order_export_folio_company_unique ON sale_order(company_id,export_folio) WHERE export_folio > 0')
        super().init()

    @api.depends('export_folio', 'name')
    def _compute_document_number(self):
        for order in self:
            order.export_document_number = str(order.export_folio) if order.export_folio else order.name

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            company = self.env['res.company'].browse(vals.get('company_id')) if vals.get('company_id') else self.env.company
            if vals.get('export_folio') and company.export_folio_mode == 'shared':
                vals['name'] = str(vals['export_folio'])
        return super().create(vals_list)

    @api.constrains('export_folio', 'company_id')
    def _check_folio(self):
        for order in self:
            if order.export_folio and order.export_folio < max(1, order.company_id.export_folio_initial):
                raise ValidationError(_('Ingrese un folio desde el número inicial configurado.'))

    def write(self, vals):
        if 'name' in vals and any(o.export_folio and str(o.export_folio) != vals['name'] for o in self):
            raise UserError(_('La nota de venta conserva el número de su folio comercial.'))
        if {'export_folio', 'company_id'}.intersection(vals):
            if any(o.export_folio and (o.state in ('sale', 'cancel') or
                    self.env['step.export.export'].search_count([('folio_sale_order_id', '=', o.id)])) for o in self):
                raise UserError(_('El folio vinculado o confirmado se conserva.'))
        if 'export_folio' in vals:
            for order in self:
                if order.company_id.export_folio_mode == 'shared' and order.state in ('draft','sent'):
                    if not vals['export_folio']:
                        raise ValidationError(_('El folio asignado debe ser positivo.'))
                    super(Order, order).write(dict(vals, name=str(vals['export_folio'])))
                else:
                    super(Order, order).write(vals)
            return True
        return super().write(vals)

    def action_confirm(self):
        for order in self:
            if order.company_id.export_folio_mode == 'shared' and order.step_export_sale_context and not order.export_folio:
                raise ValidationError(_('Ingrese el folio comercial manual en la nota de venta.'))
        return super().action_confirm()

    def _prepare_invoice(self):
        vals = super()._prepare_invoice()
        if self.export_folio:
            vals['export_folio_sale_order_id'] = self.id
        return vals


class Invoice(models.Model):
    _inherit = 'account.move'
    export_folio_sale_order_id = fields.Many2one('sale.order', string='Nota de venta del folio', check_company=True, copy=False)
    export_document_number = fields.Char(related='export_folio_sale_order_id.export_document_number', string='Folio comercial')

    def write(self, vals):
        if 'export_folio_sale_order_id' in vals and any(m.state != 'draft' for m in self):
            raise UserError(_('El folio comercial de una factura publicada se conserva.'))
        return super().write(vals)

    @api.constrains('export_folio_sale_order_id', 'step_export_shipment_id', 'partner_id')
    def _check_commercial_source(self):
        for move in self:
            source = move.export_folio_sale_order_id
            if source and (not source.export_folio or source.partner_id.commercial_partner_id != move.partner_id.commercial_partner_id or
                    move.step_export_shipment_id and move.step_export_shipment_id.folio_sale_order_id != source):
                raise ValidationError(_('La factura debe usar la nota de venta del mismo recibidor y embarque.'))


class Shipment(models.Model):
    _inherit = 'step.export.export'
    _check_company_auto = True
    freight_payment = fields.Selection(PAYMENT, string='Pago flete')
    booking = fields.Char(string='Booking (reserva)')
    folio_sale_order_id = fields.Many2one('sale.order', string='Nota de venta del folio', check_company=True, copy=False)
    commercial_folio = fields.Char(related='folio_sale_order_id.export_document_number', string='Folio comercial único')
    temperature = fields.Float(string='Temperatura °C')
    ventilation = fields.Char(string='Ventilación')
    controlled_atmosphere = fields.Char(string='Atmósfera controlada')
    filters = fields.Char(string='Filtros')
    thermograph_qty = fields.Integer(string='Thermos')
    port_transport_id = fields.Many2one('res.partner', string='Transporte a puerto', check_company=True)
    packing_partner_id = fields.Many2one('res.partner', string='Packing', check_company=True)
    consolidation = fields.Char(string='Consolidación')
    staking = fields.Char(string='Staking')
    logistics_operator_id = fields.Many2one('res.partner', string='Operador logístico', check_company=True)
    loading_datetime = fields.Datetime(string='Fecha y hora de carga')
    counterpart_id = fields.Many2one('res.partner', string='Contraparte', check_company=True)
    counterpart_phone = fields.Char(related='counterpart_id.phone', string='Teléfono')
    container_reference = fields.Char(string='Contenedor')
    container_qty = fields.Integer(string='Cantidad contenedores')
    gross_kg = fields.Float(string='Kg brutos')
    documentation_ids = fields.One2many('step.export.shipping.document', 'shipment_id', string='Documentación requerida', copy=True)
    freight_ids = fields.One2many('step.export.shipping.freight', 'shipment_id', string='Desglose flete', copy=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            company = self.env['res.company'].browse(vals.get('company_id')) if vals.get('company_id') else self.env.company
            source = self.env['sale.order'].browse(vals.get('folio_sale_order_id'))
            if company.export_folio_mode == 'shared':
                if not source.export_folio or source.company_id != company:
                    raise ValidationError(_('Seleccione una nota de venta con folio comercial de esta empresa.'))
                vals['shipment_number'] = str(source.export_folio)
            elif source:
                vals['shipment_number'] = str(source.export_folio)
            vals.setdefault('documentation_ids', [Command.create({'kind': key,'originals': originals,
                'copies': copies,'instructions': instructions}) for key,originals,copies,instructions in DOCUMENT_REQUIREMENTS])
        records = super().create(vals_list)
        records.action_complete_instruction_freights()
        return records

    def _instruction_documents(self):
        """The printed requirement is fixed; operational tracking stays editable."""
        labels = dict(DOCUMENTS)
        return [dict(kind=kind, name=labels[kind], originals=originals, copies=copies,
                     instructions=instructions) for kind,originals,copies,instructions in DOCUMENT_REQUIREMENTS]

    def _instruction_freight_catalog(self, create=False):
        self.ensure_one()
        catalog = self.env['step.export.exterior.expense.concept'].with_context(active_test=False)
        if create:
            self.env.cr.execute('SELECT pg_advisory_xact_lock(%s,%s)', [831003,self.company_id.id])
        concepts = catalog.search([('company_id','=',self.company_id.id)], order='id')
        result = []
        for label, aliases in FREIGHT_CONCEPTS:
            keys = {_concept_key(name) for name in (label, *aliases)}
            matches = concepts.filtered(lambda c: _concept_key(c.name) in keys)
            if len(matches) > 1:
                raise UserError(_('Hay varios conceptos de flete equivalentes a %(label)s. Revise el maestro antes de completar el instructivo.', label=label))
            if not matches and create:
                matches = catalog.create({'name':label, 'company_id':self.company_id.id})
                concepts |= matches
            result.append((label, matches))
        return result

    def action_complete_instruction_freights(self):
        """Append missing native references; never rewrite an existing payment."""
        self.check_access('write')
        if self:
            self.env.cr.execute('SELECT id FROM step_export_export WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(sorted(self.ids))])
            self.invalidate_recordset(['freight_ids'])
        for record in self:
            present = set(record.freight_ids.concept_id.ids)
            commands = [Command.create({'concept_id':concept.id,
                'sequence':index*10,'payment':record.freight_payment or 'collect'})
                for index,(_label,concept) in enumerate(record._instruction_freight_catalog(create=True),1)
                if concept.id not in present]
            if commands:
                record.write({'freight_ids':commands})
        return True

    def _instruction_freights(self):
        """Render the same core list even for legacy instructions without rows."""
        self.ensure_one()
        rows, covered = [], set()
        labels = dict(PAYMENT)
        for label, concept in self._instruction_freight_catalog():
            lines = self.freight_ids.filtered(lambda line: line.concept_id == concept) if concept else self.freight_ids.browse()
            covered.update(lines.ids)
            payments = list(dict.fromkeys(lines.mapped('payment'))) or [self.freight_payment or 'collect']
            rows.append({'name':concept.name if concept else label,
                'payment':' / '.join(labels[payment] for payment in payments),
                'collect':'collect' in payments, 'notes':'\n'.join(filter(None,lines.mapped('notes')))})
        # Preserve visibility of any extra historical concept; do not delete or
        # silently fold customer data into one of the standard references.
        rows.extend({'name':line.concept_id.name,'payment':labels[line.payment],
                     'collect':line.payment=='collect','notes':line.notes or ''}
                    for line in self.freight_ids if line.id not in covered)
        return rows

    @api.constrains('folio_sale_order_id', 'shipment_number', 'receiver_id', 'company_id')
    def _check_folio_source(self):
        for shipment in self:
            source = shipment.folio_sale_order_id
            if source and (not source.export_folio or source.company_id != shipment.company_id or
                    str(source.export_folio) != shipment.shipment_number or
                    shipment.receiver_id and shipment.receiver_id.commercial_partner_id != source.partner_id.commercial_partner_id or
                    source.step_export_shipment_id and source.step_export_shipment_id != shipment):
                raise ValidationError(_('Use el folio de una nota de venta del mismo recibidor, empresa y embarque.'))

    def write(self, vals):
        if {'folio_sale_order_id', 'shipment_number', 'company_id'}.intersection(vals) and any(s.folio_sale_order_id for s in self):
            raise UserError(_('La nota de venta y el folio del embarque se conservan.'))
        return super().write(vals)

    def _instruction_title(self):
        self.ensure_one()
        return {'sea': 'INSTRUCCIÓN DE EMBARQUE MARÍTIMO', 'air': 'INSTRUCCIÓN DE EMBARQUE AÉREO', 'land': 'INSTRUCCIÓN DE EMBARQUE TERRESTRE'}.get(self.transport_type, 'INSTRUCCIÓN DE EMBARQUE')

    @api.constrains('thermograph_qty','container_qty','gross_kg')
    def _check_shipping_counts(self):
        if any(min(r.thermograph_qty,r.container_qty,r.gross_kg)<0 for r in self):
            raise ValidationError(_('Thermos, contenedores y kg brutos no pueden ser negativos.'))


class Load(models.Model):
    _inherit = 'step.export.shipment.line'
    quality_id = fields.Many2one('step.management.fruit.quality', string='Calidad')
    label = fields.Char(string='Marca')

    @api.constrains('quality_id','shipment_id')
    def _check_quality_company(self):
        if any(r.quality_id.company_id and r.quality_id.company_id != r.shipment_id.company_id for r in self):
            raise ValidationError(_('La calidad debe pertenecer a la empresa del embarque o ser compartida.'))


class Document(models.Model):
    _name = 'step.export.shipping.document'
    _description = 'Seguimiento documental del instructivo'
    _order = 'sequence,id'
    _check_company_auto = True
    shipment_id = fields.Many2one('step.export.export', required=True, ondelete='cascade', index=True, check_company=True)
    company_id = fields.Many2one(related='shipment_id.company_id', store=True)
    sequence = fields.Integer(default=10)
    kind = fields.Selection(DOCUMENTS, string='Documento', required=True)
    originals = fields.Integer(string='Originales')
    copies = fields.Integer(string='Copias')
    instructions = fields.Text(string='Instrucciones')
    status = fields.Selection([('pending','Pendiente'), ('requested','Solicitado'), ('received','Recibido'), ('sent','Enviado')], default='pending', required=True, string='Estado')
    date = fields.Date(string='Fecha')
    responsible_id = fields.Many2one('res.users', string='Responsable')
    _sql_constraints = [('document_kind_unique','unique(shipment_id,kind)','El documento ya está en el seguimiento.')]

    @api.constrains('originals','copies')
    def _check_quantities(self):
        if any(min(r.originals,r.copies)<0 for r in self):
            raise ValidationError(_('Originales y copias deben ser mayores o iguales a cero.'))


class Freight(models.Model):
    _name = 'step.export.shipping.freight'
    _description = 'Desglose de flete del instructivo'
    _order = 'sequence,id'
    _check_company_auto = True
    shipment_id = fields.Many2one('step.export.export', required=True, ondelete='cascade', index=True, check_company=True)
    company_id = fields.Many2one(related='shipment_id.company_id', store=True)
    sequence = fields.Integer(default=10)
    concept_id = fields.Many2one('step.export.exterior.expense.concept', string='Concepto', required=True, check_company=True)
    payment = fields.Selection(PAYMENT, string='Forma de pago', required=True)
    notes = fields.Char(string='Observación')
