from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class Picking(models.Model):
    _inherit = 'stock.picking'

    step_fruit_type = fields.Selection(
        [('conventional', 'Convencional'), ('organic', 'Orgánica')], string='Tipo de fruta')

    step_fruit_contract_id = fields.Many2one(
        'step.producer.purchase.contract', string='Contrato', check_company=True)
    step_fruit_contract_date = fields.Date(compute='_compute_fruit_contract_date')
    step_fruit_origin_class_id = fields.Many2one(
        'step.management.fruit.class', string='Clase de fruta', check_company=True)

    @api.depends('scheduled_date')
    @api.depends_context('tz')
    def _compute_fruit_contract_date(self):
        for picking in self:
            picking.step_fruit_contract_date = fields.Date.context_today(picking, timestamp=picking.scheduled_date or None)

    def _fruit_contract_domain(self):
        self.ensure_one()
        day = self.step_fruit_contract_date
        return [('partner_id', '=', self.partner_id.id), ('company_id', '=', self.company_id.id),
                ('state', '=', 'confirmed'), ('is_superseded', '=', False),
                '|', ('date_start', '=', False), ('date_start', '<=', day),
                '|', ('date_end', '=', False), ('date_end', '>=', day)]

    @api.onchange('partner_id', 'company_id', 'scheduled_date')
    def _onchange_fruit_contract(self):
        for picking in self.filtered(lambda p: p.step_fruit_reception_kind == 'process'):
            contracts = self.env['step.producer.purchase.contract'].search(picking._fruit_contract_domain()) if picking.partner_id else self.env['step.producer.purchase.contract']
            if picking.step_fruit_contract_id not in contracts:
                picking.step_fruit_contract_id = contracts if len(contracts) == 1 else False

    @api.constrains('step_fruit_contract_id', 'partner_id', 'company_id', 'scheduled_date')
    def _check_fruit_contract(self):
        for picking in self.filtered(lambda p: p.step_fruit_contract_id and p.state not in ('done', 'cancel')):
            if picking.step_fruit_contract_id not in self.env['step.producer.purchase.contract'].search(picking._fruit_contract_domain()):
                raise ValidationError(_('Seleccione un contrato vigente y confirmado del productor y la empresa de la recepción.'))

    @api.constrains('step_fruit_origin_class_id', 'company_id')
    def _check_fruit_origin_company(self):
        self._check_company(['step_fruit_origin_class_id'])


class Move(models.Model):
    _inherit = 'stock.move'

    step_fruit_pallet_type_id = fields.Many2one('stock.package.type', string='Tipo pallet')
    step_fruit_pallet_qty = fields.Float(string='Cantidad tipo pallet', digits='Product Unit of Measure')
    # Physical container count: snapshot independently of measured stock weight.
    step_fruit_packaging_qty = fields.Float(
        string='Cantidad envases', compute='_compute_fruit_packaging_qty',
        inverse='_inverse_fruit_packaging_qty', store=True, digits='Product Unit of Measure')

    @api.depends('product_packaging_id')
    def _compute_fruit_packaging_qty(self):
        # Initialize once (and on packaging changes), never recompute boxes
        # because the operator adjusts actual kilos. Existing unambiguous tag
        # distributions are authoritative; otherwise retain the former display.
        for move in self:
            count = move.product_packaging_quantity
            picking = move.picking_id
            rows = self.env['step.packing.picking.tag.line']
            if picking.step_fruit_reception_kind == 'process':
                operations = picking.move_ids
                for row in picking.fruit_tag_line_ids:
                    candidates = operations
                    if row.product_id:
                        candidates = candidates.filtered(lambda m: m.product_id == row.product_id)
                    if row.packaging_id:
                        candidates = candidates.filtered(lambda m: m.product_id == row.packaging_id.product_id
                                                        and m.product_packaging_id == row.packaging_id)
                    if len(candidates) == 1 and candidates == move:
                        rows |= row
                if rows:
                    count = sum(rows.mapped('quantity'))
            move.step_fruit_packaging_qty = count

    def _inverse_fruit_packaging_qty(self):
        for move in self:
            count = move.step_fruit_packaging_qty
            if (move.state in ('done', 'cancel') or move.picking_id.step_fruit_reception_kind != 'process'
                    or count < 0 or not move.product_packaging_id):
                raise ValidationError(_('Indique un embalaje en una recepción a proceso abierta y una cantidad de envases no negativa.'))
            packaging = move.product_packaging_id
            move.quantity = move.product_id.uom_id._compute_quantity(packaging.qty * count, move.product_uom, round=False)

    @api.constrains('step_fruit_pallet_qty')
    def _check_fruit_pallet_qty(self):
        if any(move.step_fruit_pallet_qty < 0 for move in self):
            raise ValidationError(_('La cantidad de pallets no puede ser negativa.'))


class TagLine(models.Model):
    _inherit = 'step.packing.picking.tag.line'

    step_kg_per_box = fields.Float(string='Kg x caja', compute='_compute_kg_per_box', digits=(16, 2))

    @api.depends('kilos', 'quantity')
    def _compute_kg_per_box(self):
        for row in self:
            row.step_kg_per_box = row.kilos / row.quantity if row.quantity else 0.0
