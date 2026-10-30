from odoo import models


class Picking(models.Model):
    _inherit = 'stock.picking'

    def _step_is_fruit_receipt(self):
        self.ensure_one()
        self.check_access('read')
        return self.picking_type_code == 'incoming' and self.step_fruit_reception_kind in ('process', 'packed')

    def _get_report_lang(self):
        # This local receipt follows the Spanish Chilean form even when the
        # operator or vendor uses English. Other stock reports retain native
        # partner/user language selection.
        if self._step_is_fruit_receipt():
            for code in ('es_CL','es_ES'):
                if self.env['res.lang'].search_count([('code','=',code),('active','=',True)]):
                    return code
        return super()._get_report_lang()

    def _step_receipt_operations(self):
        self.ensure_one()
        self.check_access('read')
        return self.move_ids.filtered(lambda m: m.state != 'cancel').sorted(lambda m: (m.sequence, m.id))

    def _step_receipt_totals(self):
        self.ensure_one()
        self.check_access('read')
        moves = self._step_receipt_operations()
        units = {}
        for move in moves:
            entry = units.setdefault(move.product_uom.id, {'uom': move.product_uom, 'ordered': 0.0, 'received': 0.0})
            entry['ordered'] += move.product_uom_qty
            entry['received'] += move.quantity
        lines = self.fruit_tag_line_ids
        boxes = sum(lines.mapped('quantity'))
        net = sum(lines.mapped('kilos'))
        return {
            'pallets': sum(moves.mapped('step_fruit_pallet_qty')),
            'containers': sum(moves.mapped('step_fruit_packaging_qty')),
            'units': list(units.values()),
            'boxes': boxes, 'gross': sum(lines.mapped('gross_kg')),
            'tare': sum(lines.mapped('tare_kg')), 'net': net,
            'average': net / boxes if boxes else 0.0,
        }
