from collections import defaultdict

from odoo import _, api, Command, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.float_utils import float_compare
from odoo.tools.misc import clean_context


_REVERSE = object()
_AUDIT = {'step_fruit_reversal_id', 'step_fruit_correction_of_id', 'step_fruit_reversal_reason'}


class Picking(models.Model):
    _inherit = 'stock.picking'

    step_fruit_reversal_id = fields.Many2one('stock.picking', string='Devolución de corrección',
        readonly=True, copy=False, check_company=True, ondelete='restrict')
    step_fruit_correction_of_id = fields.Many2one('stock.picking', string='Recepción corregida',
        readonly=True, copy=False, check_company=True, ondelete='restrict', index=True)
    step_fruit_reversal_reason = fields.Char(string='Motivo de la reversión', readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('_step_fruit_reverse') is not _REVERSE and (
                any(_AUDIT & vals.keys() for vals in vals_list)
                or any(self.env.context.get('default_' + name) for name in _AUDIT)):
            raise AccessError(_('Las referencias de reversión se generan al corregir la recepción.'))
        return super().create(vals_list)

    def write(self, vals):
        if self.env.context.get('_step_fruit_reverse') is not _REVERSE and _AUDIT & vals.keys():
            raise AccessError(_('Las referencias de reversión se conservan.'))
        return super().write(vals)

    def _check_fruit_reversal(self):
        self.ensure_one()
        self.check_access('write')
        if not self.env.user.has_group('stock.group_stock_manager') or self.company_id != self.env.company:
            raise AccessError(_('La corrección requiere un responsable de Inventario de la empresa activa.'))
        if (self.state != 'done' or self.step_fruit_reception_kind != 'process'
                or self.picking_type_code != 'incoming' or self.step_fruit_reversal_id
                or self.location_id.usage != 'supplier' or self.location_dest_id.usage != 'internal'):
            raise UserError(_('Seleccione una recepción de fruta a proceso realizada, vigente y recibida de un proveedor.'))

    def action_step_reverse_fruit_receipt(self):
        self._check_fruit_reversal()
        return {'type': 'ir.actions.act_window', 'name': _('Corregir recepción realizada'),
                'res_model': 'step.fruit.receipt.reversal', 'view_mode': 'form', 'target': 'new',
                'context': {'default_picking_id': self.id}}

    def _fruit_reversal_lines(self, tags):
        self.ensure_one()
        producer = self.fruit_fundo_id.partner_id
        moves = self.move_ids.filtered(lambda move: move.state == 'done')
        lines = moves.move_line_ids.filtered(lambda line: line.quantity > 0)
        if (not tags or not lines or lines.result_package_id != tags or not producer
                or len(self.fruit_tag_line_ids) != len(tags) or tags.step_process_reception_id != self
                or any(tag.step_tag_kind != 'C' or tag.step_tag_state != 'validated'
                       or tag.company_id != self.company_id for tag in tags)
                or any(line.package_id or not line.result_package_id or line.owner_id != producer
                       or line.location_id != self.location_id or line.location_dest_id != self.location_dest_id
                       for line in lines)):
            raise UserError(_('La recepción debe conservar sus tarjas C, lotes y propietario originales.'))
        if (moves.move_dest_ids.filtered(lambda move: move.state != 'cancel')
                or moves.returned_move_ids.filtered(lambda move: move.state != 'cancel')
                or moves.stock_valuation_layer_ids
                or ('purchase_line_id' in moves._fields and moves.purchase_line_id)
                or self.step_container_transfer_ids
                or ('step.dispatch.guide' in self.env and self.env['step.dispatch.guide'].sudo().search_count(
                    [('picking_id', '=', self.id)], limit=1))):
            raise UserError(_('La recepción tiene devoluciones, documentos, valoración o traslados vinculados.'))
        purchase = self.env['purchase.order'].sudo()
        if 'step_fruit_receipt_ids' in purchase._fields and purchase.search_count([
                ('step_fruit_receipt_ids', 'in', self.ids), ('step_fruit_state', '!=', 'cancel'),
        ], limit=1):
            raise UserError(_('La recepción está vinculada a una proforma activa.'))
        history = self.env['stock.move.line'].sudo().search([
            ('state', '!=', 'cancel'), '|', ('package_id', 'in', tags.ids), ('result_package_id', 'in', tags.ids),
        ])
        if history - lines:
            raise UserError(_('Las tarjas tienen movimientos posteriores a la recepción.'))
        expected, actual = defaultdict(float), defaultdict(float)
        for line in lines:
            key = (line.result_package_id, line.product_id, line.lot_id, line.owner_id)
            expected[key] += line.product_uom_id._compute_quantity(line.quantity, line.product_id.uom_id, round=False)
        for quant in tags.quant_ids.filtered(lambda q: q.quantity or q.reserved_quantity):
            if (quant.location_id != self.location_dest_id or quant.company_id != self.company_id
                    or quant.reserved_quantity or quant.quantity <= 0):
                raise UserError(_('Las tarjas deben estar completas, sin reservas y en la ubicación de recepción.'))
            actual[quant.package_id, quant.product_id, quant.lot_id, quant.owner_id] += quant.quantity
        if expected.keys() != actual.keys() or any(
                float_compare(actual[key], quantity, precision_rounding=key[1].uom_id.rounding)
                for key, quantity in expected.items()):
            raise UserError(_('El stock disponible no coincide con la recepción original.'))
        return lines

    def _make_fruit_receipt_return(self, lines):
        self.ensure_one()
        return_type = self.picking_type_id.return_picking_type_id or self.picking_type_id
        reversal = self.env['stock.picking'].create({
            'picking_type_id': return_type.id, 'company_id': self.company_id.id, 'partner_id': self.partner_id.id,
            'location_id': self.location_dest_id.id, 'location_dest_id': self.location_id.id,
            'return_id': self.id, 'origin': _('Corrección de %s', self.name), 'step_fruit_reception_kind': False,
        })
        for original, details in lines.grouped('move_id').items():
            quantity = sum(line.product_uom_id._compute_quantity(line.quantity, original.product_uom, round=False)
                           for line in details)
            move = self.env['stock.move'].create({
                'name': original.name, 'picking_id': reversal.id, 'company_id': self.company_id.id,
                'product_id': original.product_id.id, 'product_uom': original.product_uom.id,
                'product_uom_qty': quantity, 'origin_returned_move_id': original.id,
                'location_id': reversal.location_id.id, 'location_dest_id': reversal.location_dest_id.id,
            })
            move._action_confirm(merge=False)
            move._do_unreserve()
            self.env['stock.move.line'].create([{
                'move_id': move.id, 'picking_id': reversal.id, 'company_id': self.company_id.id,
                'product_id': line.product_id.id, 'product_uom_id': line.product_uom_id.id,
                'quantity': line.quantity, 'lot_id': line.lot_id.id, 'owner_id': line.owner_id.id,
                'package_id': line.result_package_id.id, 'picked': True,
                'location_id': reversal.location_id.id, 'location_dest_id': reversal.location_dest_id.id,
            } for line in details])
        reversal.button_validate()
        if (reversal.state != 'done' or reversal.move_ids.stock_valuation_layer_ids
                or any(q.quantity or q.reserved_quantity for q in lines.result_package_id.quant_ids)):
            raise UserError(_('La devolución debe retirar todas las tarjas sin generar valoración de fruta de tercero.'))
        return reversal

    def _make_corrected_receipt(self, lines):
        rows = self.fruit_tag_line_ids.copy_data({'package_id': False, 'step_import_stock_quantity': 0})
        values = {'move_ids': [], 'fruit_tag_line_ids': [Command.create(row) for row in rows],
                  'return_id': False, 'backorder_id': False, 'step_fruit_correction_of_id': self.id,
                  'step_fruit_reception_kind': self.step_fruit_reception_kind, 'scheduled_date': self.scheduled_date}
        if 'step_external_reception_folio' in self._fields:
            values['step_external_reception_folio'] = self.step_external_reception_folio
        draft = self.copy(values)
        self.env['stock.move'].create([{
            'name': move.name, 'picking_id': draft.id, 'company_id': draft.company_id.id,
            'product_id': move.product_id.id, 'product_uom': move.product_uom.id,
            'product_uom_qty': move.quantity, 'quantity': move.quantity, 'product_packaging_id': move.product_packaging_id.id,
            'step_fruit_pallet_type_id': move.step_fruit_pallet_type_id.id,
            'step_fruit_pallet_qty': move.step_fruit_pallet_qty,
            'step_fruit_manual_container_qty': move.step_fruit_manual_container_qty,
            'location_id': move.location_id.id, 'location_dest_id': move.location_dest_id.id,
        } for move in lines.move_id])
        if draft.state != 'draft':
            raise UserError(_('La corrección debe quedar en borrador.'))
        return draft


class FruitReceiptReversal(models.TransientModel):
    _name = 'step.fruit.receipt.reversal'
    _description = 'Corregir una recepción de fruta realizada'
    _allow_sudo_commands = False

    picking_id = fields.Many2one('stock.picking', string='Recepción', required=True, readonly=True)
    reason = fields.Char(string='Motivo', required=True)

    def action_apply(self):
        self.ensure_one()
        self.check_access('write')
        picking = self.picking_id.with_context(clean_context(self.env.context), _step_fruit_reverse=_REVERSE)
        picking._check_fruit_reversal()
        if not (self.reason or '').strip():
            raise UserError(_('Indique el motivo de la corrección.'))
        with self.env.cr.savepoint():
            tags = picking.fruit_tag_line_ids.package_id
            for name in sorted(set(tags.mapped('name'))):
                self.env.cr.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ['steps-process-tag:' + name])
            checks = self.env['step.reception.product.correction'].new({'picking_id': picking.id})
            checks._lock_sources(tags)
            picking._check_fruit_reversal()
            checks._check_unused(tags)
            lines = picking._fruit_reversal_lines(tags)
            reversal = picking._make_fruit_receipt_return(lines)
            tags.write({'step_tag_state': 'void'})
            picking.write({'step_fruit_reversal_id': reversal.id, 'step_fruit_reversal_reason': self.reason.strip()})
            draft = picking._make_corrected_receipt(lines)
        return {'type': 'ir.actions.act_window', 'res_model': 'stock.picking', 'res_id': draft.id,
                'views': [(self.env.ref('step_packing_reception_revision.view_process_reception_form').id, 'form')]}
