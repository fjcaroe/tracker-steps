"""Native purchase orders used as immutable, non-stock fruit proformas."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_round
from odoo.addons.step_packing_operations.models.contract_valuation import _VALUATION
from odoo.addons.step_packing_operations.models.process_control import _INTERNAL

from .guards import _FRUIT


def _internal(record):
    return record.env.context.get('_fruit_proforma') is _FRUIT


def _controlled(record):
    return record.with_context(_fruit_proforma=_FRUIT, tracking_disable=True,
        mail_notrack=True, mail_create_nosubscribe=True, mail_notify_force_send=False)


def _ordinary_price(record, values):
    values = dict(values)
    if 'price_unit' in values:
        values['price_unit'] = float_round(float(values['price_unit'] or 0),
            precision_digits=record.env['decimal.precision'].precision_get('Product Price'))
    return values


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    step_fruit_proforma = fields.Boolean('Proforma de fruta', readonly=True, copy=False, index=True)
    step_fruit_state = fields.Selection([
        ('draft', 'Borrador'), ('approved', 'Aprobada'),
        ('invoiced', 'Facturada'), ('cancel', 'Cancelada')],
        string='Estado de proforma', default='draft', readonly=True, copy=False, index=True)
    step_fruit_species_id = fields.Many2one('step.especie', string='Especie', readonly=True)
    step_fruit_dte_code = fields.Selection([('33', 'Factura electrónica (33)'),
        ('46', 'Factura de compra electrónica (46)')], string='Documento previsto', readonly=True)
    step_fruit_period_start = fields.Date('Desde', readonly=True)
    step_fruit_period_end = fields.Date('Hasta', readonly=True)
    step_fruit_contract_ids = fields.Many2many('step.producer.purchase.contract',
        'step_fruit_proforma_contract_rel', 'order_id', 'contract_id', string='Contratos', readonly=True)
    step_fruit_tag_ids = fields.Many2many('stock.quant.package',
        'step_fruit_proforma_tag_rel', 'order_id', 'package_id', string='Tarjas', readonly=True)
    step_fruit_production_ids = fields.Many2many('step.packing.production',
        'step_fruit_proforma_production_rel', 'order_id', 'production_id', string='Órdenes de trabajo', readonly=True)
    step_fruit_withholding_tax_id = fields.Many2one('account.tax', string='Retención', readonly=True, check_company=True)
    step_fruit_guide_refs = fields.Text('Guías de recepción', readonly=True)
    step_fruit_supplier_invoice_received = fields.Boolean('Factura recibida del proveedor', copy=False)
    step_fruit_supplier_document_number = fields.Char(related='partner_ref',
        string='Número de factura del proveedor', readonly=False)
    step_fruit_approval_reference = fields.Char('Referencia de aprobación', copy=False)
    step_fruit_generated_move_ids = fields.One2many('account.move', 'step_fruit_proforma_id',
        string='Facturas generadas', readonly=True, copy=False)
    step_fruit_legacy_move_ids = fields.Many2many('account.move',
        'step_fruit_proforma_legacy_move_rel', 'order_id', 'move_id',
        string='Facturas anteriores canceladas', readonly=True, copy=False)

    _FRUIT_SOURCE_FIELDS = {
        'name', 'partner_id', 'company_id', 'currency_id', 'order_line', 'date_order',
        'payment_term_id', 'fiscal_position_id', 'picking_type_id', 'dest_address_id',
        'incoterm_id', 'origin', 'state', 'date_approve', 'amount_untaxed', 'amount_tax',
        'amount_total', 'amount_total_cc', 'currency_rate', 'tax_totals',
        'step_fruit_state', 'step_fruit_species_id', 'step_fruit_dte_code',
        'step_fruit_period_start', 'step_fruit_period_end', 'step_fruit_contract_ids',
        'step_fruit_tag_ids', 'step_fruit_production_ids', 'step_fruit_withholding_tax_id',
        'step_fruit_guide_refs', 'step_fruit_generated_move_ids', 'step_fruit_legacy_move_ids',
    }

    @api.model_create_multi
    def create(self, vals_list):
        flagged = []
        for values in vals_list:
            flagged.append(bool(values.get('step_fruit_proforma', self.env.context.get('default_step_fruit_proforma'))))
            if flagged[-1] and not _internal(self):
                raise UserError(_('Prepare la proforma desde la compra mensual de fruta.'))
        if any(flagged):
            if not all(flagged):
                raise UserError(_('Prepare las proformas por separado de las compras ordinarias.'))
            return super(PurchaseOrder, _controlled(self)).create(vals_list)
        return super().create(vals_list)

    def write(self, values):
        if 'step_fruit_proforma' in values and any(
                order.step_fruit_proforma != bool(values['step_fruit_proforma']) for order in self):
            raise UserError(_('No se cambia el tipo de una orden de compra existente.'))
        fruit = self.filtered('step_fruit_proforma')
        if fruit and not _internal(self):
            if self._FRUIT_SOURCE_FIELDS.intersection(values):
                raise UserError(_('La proforma conserva las cantidades, precios y fuentes de la compra mensual. Use sus acciones de aprobación y facturación.'))
            if any(order.step_fruit_state in ('invoiced', 'cancel') for order in fruit) and set(values).intersection({
                    'notes', 'partner_ref', 'step_fruit_supplier_document_number',
                    'step_fruit_supplier_invoice_received', 'step_fruit_approval_reference'}):
                raise UserError(_('No modifique una proforma facturada o cancelada.'))
        return super().write(values)

    def copy(self, default=None):
        if any(order.step_fruit_proforma for order in self):
            raise UserError(_('Prepare otra proforma desde las fuentes mensuales; no duplique documentos vinculados a tarjas.'))
        return super().copy(default)

    def unlink(self):
        if any(order.step_fruit_proforma for order in self) and not self.env.context.get('module_uninstall'):
            raise UserError(_('Cancele la proforma para conservar sus tarjas y documentos históricos.'))
        return super().unlink()

    def _fruit_lock(self):
        fruit = self.filtered('step_fruit_proforma')
        fruit.check_access('write')
        fruit.flush_recordset()
        # Match the monthly source lock order: OT, packages, then proforma.
        fruit.step_fruit_production_ids._lock_process()
        tags = fruit.step_fruit_tag_ids
        if tags:
            self.env.cr.execute('SELECT id FROM stock_quant_package WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(tags.ids)])
        if fruit:
            self.env.cr.execute('SELECT id FROM purchase_order WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(fruit.ids)])
            fruit.invalidate_recordset()
            fruit.order_line.invalidate_recordset(['qty_invoiced', 'qty_to_invoice', 'invoice_lines'])
        return fruit

    def _fruit_action(self):
        action = self.env['ir.actions.act_window']._for_xml_id('step_packing_fruit_proforma.fruit_proforma_action')
        if len(self) == 1:
            action.update(res_id=self.id, view_mode='form', views=[(
                self.env.ref('step_packing_fruit_proforma.fruit_proforma_form').id, 'form')])
        else:
            action['domain'] = [('id', 'in', self.ids), ('step_fruit_proforma', '=', True)]
        return action

    @api.depends('order_line.invoice_lines.move_id', 'step_fruit_generated_move_ids')
    def _compute_invoice(self):
        super()._compute_invoice()
        for order in self.filtered('step_fruit_proforma'):
            order.invoice_ids |= order.step_fruit_generated_move_ids
            order.invoice_count = len(order.invoice_ids)

    def _fruit_check_sources(self):
        self.ensure_one()
        if not self.step_fruit_proforma:
            raise UserError(_('Esta acción corresponde a una proforma de fruta.'))
        if (not self.partner_id or not self.step_fruit_species_id or not self.order_line.filtered(lambda line: not line.display_type)
                or not self.step_fruit_tag_ids or self.step_fruit_dte_code not in ('33', '46')):
            raise ValidationError(_('La proforma debe identificar productor, especie, tarjas, productos y tipo de documento.'))
        if (not self.step_fruit_period_start or not self.step_fruit_period_end
                or self.step_fruit_period_start > self.step_fruit_period_end
                or self.step_fruit_period_start.strftime('%Y-%m') != self.step_fruit_period_end.strftime('%Y-%m')):
            raise ValidationError(_('La proforma debe identificar un período válido dentro del mismo mes.'))
        if self.step_fruit_dte_code == '46' and not self.step_fruit_withholding_tax_id:
            raise ValidationError(_('La factura de compra requiere la retención configurada para la especie.'))
        if self.picking_ids or self.order_line.move_ids:
            raise UserError(_('La proforma no debe tener movimientos de inventario asociados.'))
        if any(tag.step_fruit_proforma_id != self for tag in self.step_fruit_tag_ids):
            raise UserError(_('Las tarjas deben conservar su vínculo con esta proforma. Revise sus fuentes mensuales.'))
        if any(line.product_qty <= 0 for line in self.order_line.filtered(lambda line: not line.display_type)):
            raise ValidationError(_('Las cantidades de la proforma deben ser positivas.'))
        if self.amount_total < 0:
            raise ValidationError(_('Revise los impuestos y retenciones: la proforma no puede tener un total negativo.'))

    def action_fruit_approve(self):
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(_('La aprobación de proformas requiere un responsable de Contabilidad.'))
        for order in self._fruit_lock():
            order._fruit_check_sources()
            if order.step_fruit_state == 'approved':
                continue
            if order.step_fruit_state != 'draft':
                raise UserError(_('Solo se aprueban proformas en borrador.'))
            _controlled(order).write({'state': 'purchase', 'date_approve': fields.Datetime.now(),
                                      'step_fruit_state': 'approved'})
        return True

    def button_confirm(self):
        fruit = self.filtered('step_fruit_proforma')
        if fruit:
            fruit.action_fruit_approve()
        ordinary = self - fruit
        return super(PurchaseOrder, ordinary).button_confirm() if ordinary else True

    def button_approve(self, force=False):
        fruit = self.filtered('step_fruit_proforma')
        if fruit:
            fruit.action_fruit_approve()
        ordinary = self - fruit
        return super(PurchaseOrder, ordinary).button_approve(force=force) if ordinary else {}

    def _create_picking(self):
        ordinary = self.filtered(lambda order: not order.step_fruit_proforma)
        return super(PurchaseOrder, ordinary)._create_picking() if ordinary else True

    def _add_supplier_to_product(self):
        ordinary = self.filtered(lambda order: not order.step_fruit_proforma)
        return super(PurchaseOrder, ordinary)._add_supplier_to_product() if ordinary else None

    def action_rfq_send(self):
        if any(order.step_fruit_proforma for order in self):
            raise UserError(_('Use la vista previa o impresión de la proforma de fruta.'))
        return super().action_rfq_send()

    def print_quotation(self):
        if any(order.step_fruit_proforma for order in self):
            return self.env.ref('step_packing_fruit_proforma.action_report_fruit_proforma').report_action(self)
        return super().print_quotation()

    def _fruit_check_conversion(self):
        self.ensure_one()
        self._fruit_check_sources()
        if self.step_fruit_state not in ('approved', 'invoiced') or self.state not in ('purchase', 'done'):
            raise UserError(_('Apruebe la proforma antes de preparar su factura.'))
        if self.step_fruit_dte_code == '33' and (not self.step_fruit_supplier_invoice_received or not (self.partner_ref or '').strip()):
            raise UserError(_('Confirme la recepción de la factura del proveedor e indique su número antes de preparar el DTE 33.'))

    def _prepare_invoice(self):
        values = super()._prepare_invoice()
        if not self.step_fruit_proforma:
            return values
        self._fruit_check_conversion()
        xmlid = {'33': 'l10n_cl.dc_a_f_dte', '46': 'l10n_cl.dc_fc_f_dte'}[self.step_fruit_dte_code]
        document = self.env.ref(xmlid, raise_if_not_found=False)
        if not document or 'l10n_latam_document_type_id' not in self.env['account.move']._fields:
            raise UserError(_('La compañía debe disponer del tipo de documento fiscal chileno seleccionado.'))
        journal = self.company_id.step_packing_purchase_journal_id
        if not journal:
            raise UserError(_('Configure el diario de compra de fruta en la compañía.'))
        if journal.currency_id and journal.currency_id != self.currency_id:
            raise UserError(_('El diario de compra debe permitir la moneda de la proforma.'))
        values.update(move_type='in_invoice', journal_id=journal.id,
            state='draft', invoice_date=self.step_fruit_period_end, step_fruit_proforma_id=self.id,
            l10n_latam_document_type_id=document.id,
            l10n_latam_document_number=(self.partner_ref or '').strip() if self.step_fruit_dte_code == '33' else False)
        return values

    def action_fruit_convert(self):
        return self.action_create_invoice()

    def action_create_invoice(self):
        fruit = self.filtered('step_fruit_proforma')
        if not fruit:
            return super().action_create_invoice()
        if len(fruit) != len(self):
            raise UserError(_('Prepare las facturas de proformas por separado de las órdenes de compra ordinarias.'))
        if not self.env.user.has_group('account.group_account_user'):
            raise UserError(_('La preparación de facturas requiere permisos de Contabilidad.'))
        bills = self.env['account.move']
        for order in fruit._fruit_lock():
            order._fruit_check_conversion()
            active = order.invoice_ids.filtered(lambda move: move.state != 'cancel' and move.move_type == 'in_invoice')
            if len(active) > 1:
                raise UserError(_('La proforma tiene más de una factura activa; revise los documentos antes de continuar.'))
            if active:
                order._fruit_link_productions(active)
                if order.step_fruit_state != 'invoiced':
                    _controlled(order).write({'step_fruit_state': 'invoiced'})
                bills |= active
                continue
            if order.invoice_ids.filtered(lambda move: move.state != 'cancel' and move.move_type != 'in_invoice'):
                raise UserError(_('Revise las notas de crédito vinculadas antes de preparar otra factura de la proforma.'))
            order._fruit_check_existing_production_bills()
            if order.step_fruit_state == 'invoiced':
                _controlled(order).write({'step_fruit_state': 'approved'})
            # Each PO is passed separately: native batch grouping does not include DTE type.
            super(PurchaseOrder, _controlled(order)).action_create_invoice()
            order.invalidate_recordset(['invoice_ids', 'step_fruit_generated_move_ids'])
            created = order.invoice_ids.filtered(lambda move: move.state != 'cancel')
            if len(created) != 1 or created.state != 'draft':
                raise UserError(_('La conversión debe preparar una única factura en borrador.'))
            order._fruit_link_productions(created)
            _controlled(order).write({'step_fruit_state': 'invoiced'})
            bills |= created
        return self.action_view_invoice(bills)

    def _fruit_check_existing_production_bills(self, bill=False):
        self.ensure_one()
        conflicts = self.step_fruit_production_ids.filtered(
            lambda production: production.purchase_bill_id and production.purchase_bill_id.state != 'cancel'
            and production.purchase_bill_id != bill)
        if conflicts:
            raise UserError(_('Las OT %s ya tienen otra factura activa. Revise sus documentos antes de convertir la proforma.') % ', '.join(conflicts.mapped('name')))

    def _fruit_link_productions(self, bill):
        self.ensure_one()
        self._fruit_check_existing_production_bills(bill)
        _controlled(self.step_fruit_production_ids).with_context(
            _packing_valuation=_VALUATION, _packing_control=_INTERNAL).write({'purchase_bill_id': bill.id})

    def button_cancel(self):
        fruit = self.filtered('step_fruit_proforma')
        for order in fruit._fruit_lock():
            if any(move.state != 'cancel' for move in order.invoice_ids | order.step_fruit_legacy_move_ids):
                raise UserError(_('Cancele las facturas vinculadas antes de cancelar la proforma.'))
            if order.picking_ids or order.order_line.move_ids:
                raise UserError(_('Revise los movimientos de inventario asociados antes de cancelar.'))
            super(PurchaseOrder, _controlled(order)).button_cancel()
            _controlled(order).write({'step_fruit_state': 'cancel'})
            linked = order.step_fruit_tag_ids.filtered(lambda tag: tag.step_fruit_proforma_id == order)
            _controlled(linked).write({'step_fruit_proforma_id': False})
        ordinary = self - fruit
        return super(PurchaseOrder, ordinary).button_cancel() if ordinary else True

    def button_draft(self):
        if any(order.step_fruit_proforma for order in self):
            raise UserError(_('Una proforma cancelada conserva su historial; prepare otra desde la compra mensual.'))
        return super().button_draft()


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    price_unit = fields.Float(digits=(24, 12))
    step_fruit_variety_id = fields.Many2one('step.variedad', string='Variedad', readonly=True)
    step_fruit_expense_account_id = fields.Many2one('account.account', string='Cuenta de compra', readonly=True, check_company=True)
    step_fruit_contract_line_ids = fields.Many2many('step.producer.purchase.contract.product',
        'step_fruit_proforma_contract_line_rel', 'line_id', 'contract_line_id', string='Precios de contrato', readonly=True)
    step_fruit_tag_line_ids = fields.Many2many('step.fruit.package.line',
        'step_fruit_proforma_tag_line_rel', 'line_id', 'tag_line_id', string='Detalle de tarjas', readonly=True)
    step_fruit_source_rows = fields.Json('Anexo de origen', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        normalized = []
        for values in vals_list:
            order = self.env['purchase.order'].browse(values.get('order_id') or self.env.context.get('default_order_id'))
            if order.step_fruit_proforma and not _internal(self):
                raise UserError(_('Los productos de la proforma proceden de las tarjas mensuales.'))
            normalized.append(values if order.step_fruit_proforma else _ordinary_price(self, values))
        return super().create(normalized)

    def write(self, values):
        fruit = self.filtered(lambda line: line.order_id.step_fruit_proforma)
        target = self.env['purchase.order'].browse(values.get('order_id'))
        if (fruit or target.step_fruit_proforma) and not _internal(self):
            raise UserError(_('No modifique las líneas de la proforma; conserve la revisión de sus fuentes mensuales.'))
        if 'price_unit' in values:
            ordinary = self - fruit
            if ordinary:
                super(PurchaseOrderLine, ordinary).write(_ordinary_price(self, values))
            return super(PurchaseOrderLine, fruit).write(values) if fruit else True
        return super().write(values)

    @api.depends('product_qty', 'product_uom', 'company_id', 'order_id.partner_id')
    def _compute_price_unit_and_date_planned_and_name(self):
        super()._compute_price_unit_and_date_planned_and_name()
        precision = self.env['decimal.precision'].precision_get('Product Price')
        for line in self.filtered(lambda item: not item.order_id.step_fruit_proforma):
            line.price_unit = float_round(line.price_unit, precision_digits=precision)

    def unlink(self):
        if any(line.order_id.step_fruit_proforma for line in self) and not _internal(self):
            raise UserError(_('No elimine líneas de la proforma.'))
        return super().unlink()

    @api.depends('invoice_lines.move_id.state', 'invoice_lines.quantity', 'qty_received',
                 'product_uom_qty', 'order_id.state', 'order_id.step_fruit_state', 'order_id.step_fruit_proforma')
    def _compute_qty_invoiced(self):
        super()._compute_qty_invoiced()
        for line in self.filtered(lambda item: item.order_id.step_fruit_proforma):
            line.qty_to_invoice = (line.product_qty - line.qty_invoiced
                if line.order_id.step_fruit_state == 'approved' and line.order_id.state in ('purchase', 'done') else 0)

    def _create_or_update_picking(self):
        ordinary = self.filtered(lambda line: not line.order_id.step_fruit_proforma)
        return super(PurchaseOrderLine, ordinary)._create_or_update_picking() if ordinary else None

    def _create_stock_moves(self, picking):
        ordinary = self.filtered(lambda line: not line.order_id.step_fruit_proforma)
        return super(PurchaseOrderLine, ordinary)._create_stock_moves(picking) if ordinary else self.env['stock.move']

    def _prepare_account_move_line(self, move=False):
        values = super()._prepare_account_move_line(move=move)
        if self.order_id.step_fruit_proforma and self.step_fruit_expense_account_id:
            fiscal = move.fiscal_position_id if move else self.order_id.fiscal_position_id
            values['account_id'] = fiscal.map_account(self.step_fruit_expense_account_id).id
        return values


class FruitPackage(models.Model):
    _inherit = 'stock.quant.package'

    step_fruit_proforma_id = fields.Many2one('purchase.order', string='Proforma de compra de fruta',
        readonly=True, copy=False, index=True, ondelete='restrict', check_company=True,
        domain="[('step_fruit_proforma','=',True)]")

    @api.model_create_multi
    def create(self, vals_list):
        if any(values.get('step_fruit_proforma_id', self.env.context.get('default_step_fruit_proforma_id'))
               for values in vals_list) and not _internal(self):
            raise UserError(_('La proforma se vincula desde la compra mensual.'))
        return super().create(vals_list)

    def write(self, values):
        if 'step_fruit_proforma_id' in values and not _internal(self):
            raise UserError(_('La proforma se vincula desde la compra mensual.'))
        return super().write(values)


class AccountMove(models.Model):
    _inherit = 'account.move'

    step_fruit_proforma_id = fields.Many2one('purchase.order', string='Proforma de fruta',
        readonly=True, copy=False, index=True, ondelete='restrict', check_company=True)
    step_fruit_migrated_proforma_id = fields.Many2one('purchase.order', string='Proforma de sustitución',
        readonly=True, copy=False, index=True, ondelete='restrict', check_company=True)

    @api.model_create_multi
    def create(self, vals_list):
        if any(values.get('step_fruit_proforma_id', self.env.context.get('default_step_fruit_proforma_id'))
               or values.get('step_fruit_migrated_proforma_id', self.env.context.get('default_step_fruit_migrated_proforma_id'))
               for values in vals_list) and not _internal(self):
            raise UserError(_('El vínculo de proforma se genera desde su conversión o revisión autorizada.'))
        self.env['purchase.order'].browse([values.get('step_fruit_proforma_id', self.env.context.get('default_step_fruit_proforma_id'))
            for values in vals_list if values.get('step_fruit_proforma_id', self.env.context.get('default_step_fruit_proforma_id'))])._fruit_lock()
        return super().create(vals_list)

    def write(self, values):
        for field in ('step_fruit_proforma_id', 'step_fruit_migrated_proforma_id'):
            if field in values and not _internal(self) and any(move[field].id != values[field] for move in self):
                raise UserError(_('No cambie el vínculo de origen de una factura de fruta.'))
        migrated = self.filtered('step_fruit_migrated_proforma_id')
        if migrated and 'state' in values and values['state'] != 'cancel':
            raise UserError(_('La factura cancelada fue sustituida por una proforma y conserva ese historial.'))
        if 'step_fruit_migrated_proforma_id' in values and any(
                move.step_fruit_migrated_proforma_id and move.step_fruit_migrated_proforma_id.id != values['step_fruit_migrated_proforma_id']
                for move in self):
            raise UserError(_('La proforma de sustitución de una factura histórica es inmutable.'))
        if 'state' in values and values['state'] != 'cancel':
            self.step_fruit_proforma_id._fruit_lock()
        return super().write(values)

    @api.constrains('step_fruit_proforma_id', 'step_fruit_migrated_proforma_id', 'state')
    def _check_fruit_proforma_links(self):
        for move in self:
            if move.step_fruit_proforma_id and not move.step_fruit_proforma_id.step_fruit_proforma:
                raise ValidationError(_('La factura debe referenciar una proforma de fruta.'))
            if move.step_fruit_proforma_id and move.state != 'cancel':
                order = move.step_fruit_proforma_id
                if order.step_fruit_state not in ('approved', 'invoiced') or order.state not in ('purchase', 'done'):
                    raise ValidationError(_('La factura requiere una proforma aprobada.'))
                if self.search_count([('step_fruit_proforma_id', '=', order.id),
                                      ('state', '!=', 'cancel'), ('id', '!=', move.id)]):
                    raise ValidationError(_('Una proforma no puede tener dos facturas activas.'))
            if move.step_fruit_migrated_proforma_id and (move.state != 'cancel' or not move.step_fruit_migrated_proforma_id.step_fruit_proforma):
                raise ValidationError(_('Solo una factura cancelada puede conservar el vínculo de sustitución por proforma.'))

    def button_draft(self):
        if any(move.step_fruit_migrated_proforma_id for move in self):
            raise UserError(_('No reactive una factura histórica sustituida por proforma.'))
        orders = self.step_fruit_proforma_id
        orders._fruit_lock()
        result = super().button_draft()
        for order in orders.filtered(lambda row: row.step_fruit_state == 'approved'):
            _controlled(order).write({'step_fruit_state': 'invoiced'})
        return result

    def action_post(self):
        if any(move.step_fruit_migrated_proforma_id for move in self):
            raise UserError(_('No contabilice una factura histórica sustituida por proforma.'))
        return super().action_post()

    def _post(self, soft=True):
        if any(move.step_fruit_migrated_proforma_id for move in self):
            raise UserError(_('No contabilice una factura histórica sustituida por proforma.'))
        return super()._post(soft=soft)

    def button_cancel(self):
        orders = self.step_fruit_proforma_id | self.invoice_line_ids.purchase_line_id.order_id.filtered('step_fruit_proforma')
        result = super().button_cancel()
        for order in orders:
            if order.step_fruit_state == 'invoiced' and not order.invoice_ids.filtered(lambda move: move.state != 'cancel'):
                _controlled(order).write({'step_fruit_state': 'approved'})
        return result

    def unlink(self):
        if any(move.step_fruit_proforma_id or move.step_fruit_migrated_proforma_id for move in self) and not self.env.context.get('module_uninstall'):
            raise UserError(_('Cancele la factura vinculada para conservar su trazabilidad.'))
        return super().unlink()


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    price_unit = fields.Float(digits=(24, 12))
    step_fruit_proforma_id = fields.Many2one(related='move_id.step_fruit_proforma_id',
        string='Proforma de fruta', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        normalized = []
        for values in vals_list:
            move = self.env['account.move'].browse(values.get('move_id') or self.env.context.get('default_move_id'))
            source = self.env['purchase.order.line'].browse(values.get('purchase_line_id') or self.env.context.get('default_purchase_line_id'))
            reversal = (source.order_id.step_fruit_proforma and move.move_type == 'in_refund'
                        and move.reversed_entry_id.step_fruit_proforma_id == source.order_id)
            if source.order_id.step_fruit_proforma and not _internal(self) and not reversal:
                raise UserError(_('Vincule las líneas de compra desde la conversión de su proforma aprobada.'))
            normalized.append(values if move.step_fruit_proforma_id or reversal else _ordinary_price(self, values))
        return super().create(normalized)

    def write(self, values):
        if 'purchase_line_id' in values and not _internal(self):
            source = self.env['purchase.order.line'].browse(values['purchase_line_id'])
            if source.order_id.step_fruit_proforma or any(
                    line.purchase_line_id.order_id.step_fruit_proforma
                    and line.purchase_line_id.id != values['purchase_line_id'] for line in self):
                raise UserError(_('No cambie la línea de origen de una factura vinculada a proforma.'))
        if 'price_unit' in values:
            fruit = self.filtered(lambda line: line._fruit_preserve_price())
            ordinary = self - fruit
            if ordinary:
                super(AccountMoveLine, ordinary).write(_ordinary_price(self, values))
            return super(AccountMoveLine, fruit).write(values) if fruit else True
        return super().write(values)

    @api.constrains('purchase_line_id', 'move_id')
    def _check_fruit_purchase_source(self):
        for line in self.filtered(lambda row: row.purchase_line_id.order_id.step_fruit_proforma):
            source = line.purchase_line_id.order_id
            reversal = line.move_id.move_type == 'in_refund' and line.move_id.reversed_entry_id.step_fruit_proforma_id == source
            if source != line.move_id.step_fruit_proforma_id and not reversal:
                raise ValidationError(_('La línea de compra debe pertenecer a la proforma de la factura.'))

    def _fruit_preserve_price(self):
        self.ensure_one()
        return bool(self.step_fruit_proforma_id or (
            self.purchase_line_id.order_id.step_fruit_proforma and self.move_id.move_type == 'in_refund'
            and self.move_id.reversed_entry_id.step_fruit_proforma_id == self.purchase_line_id.order_id))

    @api.depends('product_id', 'product_uom_id')
    def _compute_price_unit(self):
        super()._compute_price_unit()
        precision = self.env['decimal.precision'].precision_get('Product Price')
        for line in self.filtered(lambda item: not item._fruit_preserve_price()):
            line.price_unit = float_round(line.price_unit, precision_digits=precision)
