from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


def report_access():
    return AccessError(_('Esta consulta conserva las operaciones históricas de Packing.'))


class HistoricalRecord:
    # The reporting provider cannot perform stock movements or edit material reviews.
    def _check_access(self, operation):
        if operation != 'read':
            return self, report_access
        return super()._check_access(operation)

    @api.model_create_multi
    def create(self, values):
        raise report_access()

    def write(self, values):
        raise report_access()

    def unlink(self):
        raise report_access()


class PackingOrder(HistoricalRecord, models.Model):
    _auto = False
    _log_access = True
    _name = 'step.packing.order'
    _description = 'Orden de proceso de Packing'
    _inherit = ['mail.thread','mail.activity.mixin']
    _order = 'week_start desc, id desc'
    state = fields.Selection([('draft','Creada'),('validated','Validada'),('closed','Cerrada')],
                             default='draft',required=True,tracking=True,copy=False)
    week_start = fields.Date(string='Inicio semana',required=True,default=fields.Date.today)
    week_end = fields.Date(string='Fin semana',required=True,default=fields.Date.today)
    name = fields.Char(required=True, copy=False, readonly=True, default='Nuevo')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)


class PackingProduction(HistoricalRecord, models.Model):
    _auto = False
    _log_access = True
    _name = 'step.packing.production'
    _description = 'Orden de Trabajo de Packing'
    _inherit = ['mail.thread','mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(required=True, copy=False, readonly=True, default='Nuevo')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    state = fields.Selection([('created','Creada'),('validated','Validada'),('closed','Cerrada'),
        ('costed','Costeada'),('accounted','Contabilizada')], string='Estado', default='created', required=True, copy=False, tracking=True)
    date = fields.Date('Fecha de proceso', required=True, default=fields.Date.context_today)
    product_uom_id = fields.Many2one('uom.uom',string='UdM',required=True,default=lambda self: self.env.ref('uom.product_uom_unit'))
    required_inspection = fields.Selection([('none','Sin inspección obligatoria'),('internal','Interna'),('sag','SAG')],
                                            default='none',required=True,string='Inspección exigida')
    material_review_state = fields.Selection([('pending','Pendiente de preparación'),('review','En revisión'),
        ('approved','Aprobada')],string='Revisión de materiales',default='pending',required=True,copy=False)
    packing_partner_id = fields.Many2one('res.partner', string='Planta')
    fruit_grower_id = fields.Many2one('res.partner', string='Productor')
    fruit_species_id = fields.Many2one('step.especie',string='Especie')
    fruit_variety_id = fields.Many2one('step.variedad',string='Variedad',domain="[('especie_id', '=?', fruit_species_id)]")
    raw_product_id = fields.Many2one('product.product', string='Materia prima')
    step_packing_order_id = fields.Many2one('step.packing.order', string='Orden de proceso', index=True)
    started_at = fields.Datetime('Inicio')
    finished_at = fields.Datetime('Término')
    workers = fields.Integer('Dotación')
    downtime_ids = fields.One2many('step.packing.downtime','production_id',string='Detenciones')
    # Amounts are the original stored OT balance, including adjustments in later versions of Packing.
    step_packing_input_kg = fields.Float(string='Kilos a proceso',digits='Stock Weight',readonly=True,copy=False)
    step_packing_export_kg = fields.Float(string='Kilos exportación',digits='Stock Weight',readonly=True,copy=False)
    step_packing_commercial_kg = fields.Float(string='Kilos comercial',digits='Stock Weight',readonly=True,copy=False)
    step_packing_precaliber_kg = fields.Float(string='Kilos precalibre',digits='Stock Weight',readonly=True,copy=False)
    step_packing_waste_kg = fields.Float(string='Kilos desecho',digits='Stock Weight',readonly=True,copy=False)
    step_packing_loss_kg = fields.Float(string='Merma kg',digits='Stock Weight',readonly=True,copy=False)
    step_packing_export_percent = fields.Float(string='% exportación',compute='_compute_export_percent')
    effective_hours = fields.Float('Horas efectivas',compute='_compute_performance')
    kg_hour = fields.Float('Kg por hora efectiva',compute='_compute_performance')
    kg_worker_hour = fields.Float('Kg por hora-hombre efectiva',compute='_compute_performance')

    @api.depends('step_packing_export_kg','step_packing_input_kg')
    def _compute_export_percent(self):
        for row in self:
            row.step_packing_export_percent = row.step_packing_export_kg / row.step_packing_input_kg * 100 if row.step_packing_input_kg else 0

    @api.depends('started_at','finished_at','workers','downtime_ids.started_at','downtime_ids.finished_at','step_packing_input_kg')
    def _compute_performance(self):
        for row in self:
            elapsed=(row.finished_at-row.started_at).total_seconds()/3600 if row.started_at and row.finished_at else 0
            row.effective_hours=max(0,elapsed-sum(row.downtime_ids.mapped('hours')))
            row.kg_hour=row.step_packing_input_kg/row.effective_hours if row.effective_hours>0 else 0
            row.kg_worker_hour=row.kg_hour/row.workers if row.workers>0 else 0


class Downtime(HistoricalRecord, models.Model):
    _auto = False
    _log_access = True
    _name = 'step.packing.downtime'
    _description = 'Detención de línea de packing'
    production_id = fields.Many2one('step.packing.production',required=True,ondelete='cascade')
    reason_id = fields.Many2one('step.packing.stop.reason',string='Causa',required=True)
    company_id = fields.Many2one(related='production_id.company_id',store=True)
    started_at = fields.Datetime('Inicio',required=True)
    finished_at = fields.Datetime('Término',required=True)
    hours = fields.Float('Horas',compute='_compute_hours')

    @api.depends('started_at','finished_at')
    def _compute_hours(self):
        for row in self:
            row.hours=(row.finished_at-row.started_at).total_seconds()/3600 if row.started_at and row.finished_at else 0


class FruitPackageLine(HistoricalRecord, models.Model):
    _auto = False
    _log_access = True
    _name = 'step.fruit.package.line'
    _description = 'Contenido de tarja por productor'
    _order = 'id'
    package_id = fields.Many2one('stock.quant.package',required=True,ondelete='cascade',index=True)
    producer_id = fields.Many2one('res.partner',string='Productor',required=True)
    product_id = fields.Many2one('product.product',string='Producto',required=True)
    quantity = fields.Float('Cantidad',required=True,digits='Product Unit of Measure')
    kilos = fields.Float('Kilos',required=True,digits='Stock Weight')


class Package(models.Model):
    _inherit = 'stock.quant.package'

    step_tag_kind = fields.Selection([('C','Cosecha'),('E','Exportación'),('N','Nacional')],string='Tipo de tarja',index=True)
    step_tag_state = fields.Selection([('created','Creada'),('validated','Validada'),('processed','Procesada'),
        ('repalletized','Repaletizada'),('dispatched','Despachada / embarcada'),('liquidated','Liquidada'),('void','Nula')],
        string='Estado de tarja',index=True,default='created')
    step_producer_id = fields.Many2one('res.partner', string='Productor de origen',index=True)
    harvest_date = fields.Date('Fecha de cosecha')
    received_at = fields.Datetime('Recepción registrada',readonly=True,copy=False)
    step_tag_line_ids = fields.One2many('step.fruit.package.line','package_id',string='Detalle por productor')
    step_actual_kg = fields.Float(string='Kilos reales',compute='_compute_step_actual_kg',digits='Stock Weight')
    step_packaging_id = fields.Many2one('product.packaging',string='Embalaje')
    step_packing_production_id = fields.Many2one('step.packing.production',string='OT de Packing',copy=False,index=True,ondelete='restrict')
    step_packing_date = fields.Date(related='step_packing_production_id.date',string='Date Packing')
    step_packing_partner_id = fields.Many2one('res.partner',string='Packing',readonly=True,copy=False)

    @api.depends('step_tag_line_ids.kilos')
    def _compute_step_actual_kg(self):
        for tag in self:
            tag.step_actual_kg=sum(tag.step_tag_line_ids.mapped('kilos'))

    def write(self, values):
        self.check_access('write')
        if REPORT_FIELDS.intersection(values):
            raise UserError(_('El cambio de una tarja requiere el proveedor operativo de Packing.'))
        locked={'fundo_id','box_count','especie_id','variedad_id','fruit_type','fruit_category_id','fruit_caliber_id','step_packing_result'}
        if locked.intersection(values) and any(tag.is_fruit_tag and tag.step_tag_state not in ('created','void') for tag in self):
            raise UserError(_('Una tarja validada conserva sus datos de origen.'))
        return super().write(values)

    @api.model_create_multi
    def create(self, vals_list):
        if any(REPORT_FIELDS.intersection(values) or values.get('is_fruit_tag') for values in vals_list):
            raise UserError(_('El alta de tarjas requiere el proveedor operativo de Packing.'))
        return super().create(vals_list)


REPORT_FIELDS = frozenset({'step_tag_kind','step_tag_state','step_producer_id','harvest_date','received_at','step_tag_line_ids',
    'step_actual_kg','step_packaging_id','step_packing_production_id','step_packing_date','step_packing_partner_id'})
