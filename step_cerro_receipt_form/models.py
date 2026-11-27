from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from odoo.addons.step_cerro_pack_reports.models import HistoricalRecord

# The existing stock, dispatch, container and interplant fields use their
# original Steps LGPL/AGPL providers. The quality and fiscal fields implement
# the user interface observed on the archived Cerro transfers.
class ReceiptArchive(HistoricalRecord):
    def _check_removed_columns(self, log=False):
        # These are read-only projections over five tables owned by the original
        # applications. Their undisplayed fields were never removed. Odoo's
        # default implementation would relax them on every module upgrade.
        if self._auto or self._name not in {
                'quality.alert','quality.point','quality.check','step.dispatch.guide','step.harvest.container.work.order'}:
            return super()._check_removed_columns(log=log)
        return None


class Guide(ReceiptArchive, models.Model):
    _name = 'step.dispatch.guide'
    _description = 'Guía de despacho'
    _inherit = ['mail.thread','mail.activity.mixin']
    _order = 'date desc, id desc'
    _auto = False
    _log_access = True

    name = fields.Char('Referencia', default=lambda self:_('Nueva'), readonly=True, copy=False, index=True)
    date = fields.Date('Fecha de guía', default=fields.Date.context_today, required=True, tracking=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self:self.env.company, index=True)
    picking_id = fields.Many2one('stock.picking', string='Operación de inventario', copy=False)


class ContainerOrder(ReceiptArchive, models.Model):
    _name = 'step.harvest.container.work.order'
    _description = 'Orden de trabajo de envases'
    _order = 'id desc'
    _auto = False
    _log_access = True

    name = fields.Char(required=True, default='Nuevo', readonly=True, copy=False)
    company_id = fields.Many2one('res.company', required=True, default=lambda self:self.env.company)


class Point(ReceiptArchive, models.Model):
    _name = 'quality.point'
    _description = 'Quality Control Point'
    _inherit = ['mail.thread']
    _order = 'sequence, id'
    _auto = False
    _log_access = True

    name = fields.Char('Reference', required=True, copy=False, default=lambda self:_('New'))
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one('res.company', required=True, index=True, default=lambda self:self.env.company)


class Check(ReceiptArchive, models.Model):
    _name = 'quality.check'
    _description = 'Quality Check'
    _inherit = ['mail.thread','mail.activity.mixin']
    _order = 'point_id, id'
    _auto = False
    _log_access = True

    name = fields.Char('Reference', copy=False)
    company_id = fields.Many2one('res.company', required=True, index=True, default=lambda self:self.env.company)
    picking_id = fields.Many2one('stock.picking', string='Picking')
    point_id = fields.Many2one('quality.point', string='Control Point')
    quality_state = fields.Selection([('none','To do'),('pass','Passed'),('fail','Failed')],
                                     string='Status', default='none', copy=False, tracking=True)


class Alert(ReceiptArchive, models.Model):
    _name = 'quality.alert'
    _description = 'Quality Alert'
    _inherit = ['mail.thread','mail.activity.mixin']
    _auto = False
    _log_access = True

    name = fields.Char(default=lambda self:_('New'), copy=False)
    company_id = fields.Many2one('res.company', required=True, index=True, default=lambda self:self.env.company)
    picking_id = fields.Many2one('stock.picking', string='Picking')


REASONS=[('1','1. Operation is sale'),('2','2. Sales to be made'),('3','3. Consignments'),('4','4. Free delivery'),
         ('5','5. Internal Transfer'),('6','6. Other not-sale transfers'),('7','7. Return guide'),
         ('8','8. Exportation Transfers'),('9','9. Export Sales')]


class Picking(models.Model):
    _inherit = 'stock.picking'

    check_ids = fields.One2many('quality.check', 'picking_id', string='Checks')
    quality_alert_ids = fields.One2many('quality.alert', 'picking_id', string='Alerts')
    quality_alert_count = fields.Integer(compute='_compute_receipt_quality')
    quality_check_fail = fields.Boolean(compute='_compute_receipt_quality')
    l10n_cl_delivery_guide_reason = fields.Selection(REASONS, string='Reason of the Transfer', default='1')
    l10n_cl_draft_status = fields.Boolean(copy=False)
    l10n_cl_dte_file = fields.Many2one('ir.attachment', string='DTE file', copy=False)
    l10n_cl_sii_send_file = fields.Many2one('ir.attachment', string='SII Send file', copy=False)
    l10n_cl_sii_send_ident = fields.Text('SII Send Identification(Track ID)', copy=False, tracking=True)
    l10n_latam_document_type_id = fields.Many2one('l10n_latam.document.type', string='Document Type', readonly=True, copy=False)
    l10n_cl_is_return = fields.Boolean(compute='_compute_receipt_return')
    dispatch_guide_ids = fields.One2many('step.dispatch.guide', 'picking_id', string='Guías de despacho')
    dispatch_guide_count = fields.Integer(compute='_compute_dispatch_guide_count')
    step_container_work_order_id = fields.Many2one('step.harvest.container.work.order', string='OT de envases (consumo)',
                                                  copy=False, ondelete='restrict', check_company=True, index=True)
    step_interplant_guide_id = fields.Many2one('step.dispatch.guide', string='Guía interplanta', readonly=True, copy=False, ondelete='restrict')
    step_dispatch_origin_guide_id = fields.Many2one('step.dispatch.guide', readonly=True, copy=False, ondelete='restrict')
    step_interplant_tag_ids = fields.Many2many('stock.quant.package', compute='_compute_interplant_tags', string='Tarjas recibidas')
    step_product_correction_count = fields.Integer(compute='_compute_product_correction_count')

    @api.depends_context('uid','allowed_company_ids')
    @api.depends('check_ids.quality_state','quality_alert_ids','state')
    def _compute_receipt_quality(self):
        for picking in self:
            picking.quality_alert_count = len(picking.quality_alert_ids)
            picking.quality_check_fail = any(check.quality_state=='fail' for check in picking.check_ids)

    @api.depends('move_ids.origin_returned_move_id')
    def _compute_receipt_return(self):
        for picking in self:
            picking.l10n_cl_is_return = bool(picking.move_ids.origin_returned_move_id)

    @api.depends('move_line_ids.result_package_id','step_interplant_guide_id')
    def _compute_interplant_tags(self):
        for picking in self:
            picking.step_interplant_tag_ids = picking.move_line_ids.result_package_id.filtered('is_fruit_tag') if picking.step_interplant_guide_id else False

    def _compute_dispatch_guide_count(self):
        for picking in self:
            picking.dispatch_guide_count = len(picking.dispatch_guide_ids)

    def _compute_product_correction_count(self):
        counts = dict(self.env['stock.move']._read_group(
            [('step_receipt_correction_id','in',self.ids)], ['step_receipt_correction_id'], ['__count']))
        for picking in self:
            picking.step_product_correction_count = counts.get(picking, 0)

    def action_step_view_product_corrections(self):
        self.ensure_one()
        self.check_access('read')
        return {'type':'ir.actions.act_window', 'name':_('Correcciones de producto'), 'res_model':'stock.move',
                'view_mode':'list,form', 'views':[(self.env.ref('step_packing_reception_revision.receipt_product_correction_moves').id,'list'),(False,'form')],
                'domain':[('step_receipt_correction_id','=',self.id)],'context':{'create':False}}

    def action_view_dispatch_guides(self):
        self.ensure_one()
        self.check_access('read')
        return {'type':'ir.actions.act_window','name':_('Guías de despacho'),'res_model':'step.dispatch.guide',
                'view_mode':'list,form','domain':[('picking_id','=',self.id)],'context':{'default_picking_id':self.id}}

    _receipt_links = frozenset({'l10n_cl_draft_status','l10n_cl_dte_file','l10n_cl_sii_send_file','l10n_cl_sii_send_ident',
                               'l10n_latam_document_type_id','check_ids','quality_alert_ids','step_container_work_order_id',
                               'step_interplant_guide_id','step_dispatch_origin_guide_id','dispatch_guide_ids'})

    @api.model_create_multi
    def create(self,values_list):
        if any(any(values.get(k) or self.env.context.get('default_'+k) for k in self._receipt_links) for values in values_list):
            raise AccessError(_('El documento de origen genera los vínculos de esta operación.'))
        return super().create(values_list)

    def write(self,values):
        if self._receipt_links.intersection(values):
            raise AccessError(_('El documento de origen conserva los vínculos de esta operación.'))
        return super().write(values)


class Package(models.Model):
    _inherit = 'stock.quant.package'

    step_interplant_origin_tag_id = fields.Many2one('stock.quant.package', string='Tarja de origen', readonly=True, copy=False, ondelete='restrict')

    @api.model_create_multi
    def create(self,values_list):
        if self.env.context.get('default_step_interplant_origin_tag_id') or any(row.get('step_interplant_origin_tag_id') for row in values_list):
            raise AccessError(_('La guía conserva el origen de la tarja trasladada.'))
        return super().create(values_list)

    def write(self,values):
        if 'step_interplant_origin_tag_id' in values:
            raise AccessError(_('La guía conserva el origen de la tarja trasladada.'))
        if set(values).intersection({'step_process_reception_id','is_fruit_tag','name'}) and any(self.mapped('step_interplant_origin_tag_id')):
            raise AccessError(_('Conserve el folio y la recepción de origen de la tarja trasladada.'))
        return super().write(values)
