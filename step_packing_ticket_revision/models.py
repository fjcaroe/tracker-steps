from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.osv import expression


class Picking(models.Model):
    _inherit = 'stock.picking'

    step_external_reception_folio = fields.Char(string='Referencia externa', readonly=True, copy=False, index=True)
    _sql_constraints = [
        ('external_reception_folio_unique',
         'UNIQUE(company_id, step_receiving_packing_id, fruit_season_id, step_external_reception_folio)',
         'Ya existe una recepción con ese folio externo para el packing y la temporada.'),
    ]

    step_receiving_packing_id = fields.Many2one(
        'res.partner', string='Packing', check_company=True,
        domain="[('step_export_packing','=',True)]")

    step_reception_product_ids = fields.Many2many(
        'product.product', string='Producto', compute='_compute_step_reception_summary')
    step_reception_packaging_ids = fields.Many2many(
        'product.packaging', string='Embalaje', compute='_compute_step_reception_summary')
    step_reception_container_qty = fields.Float(
        string='Cantidad de envases', digits='Product Unit of Measure', compute='_compute_step_reception_summary')
    step_reception_net_kg = fields.Float(
        string='Cantidad (kg)', digits='Stock Weight', compute='_compute_step_reception_summary')
    step_reception_avg_kg = fields.Float(
        string='Peso promedio (kg/envase)', digits='Stock Weight', compute='_compute_step_reception_summary')

    @api.depends('state', 'fruit_tag_line_ids.product_id', 'fruit_tag_line_ids.packaging_id.product_id',
                 'fruit_tag_line_ids.quantity', 'fruit_tag_line_ids.kilos', 'move_ids.state',
                 'move_ids.product_id', 'move_ids.product_packaging_id', 'move_ids.step_fruit_packaging_qty',
                 'move_ids.quantity', 'move_ids.product_uom_qty', 'move_ids.product_uom')
    def _compute_step_reception_summary(self):
        kg = self.env.ref('uom.product_uom_kgm')
        for picking in self:
            rows = picking.fruit_tag_line_ids
            moves = picking.move_ids.filtered(lambda move: move.state != 'cancel')
            products = self.env['product.product']
            for row in rows:
                products |= row.product_id or row.packaging_id.product_id
            if not products or any(not (row.product_id or row.packaging_id) for row in rows):
                products |= moves.product_id
            packaging = rows.packaging_id
            if not packaging or any(not row.packaging_id for row in rows):
                packaging |= moves.product_packaging_id

            containers = sum(rows.mapped('quantity')) or sum(moves.mapped('step_fruit_packaging_qty'))
            kilos = sum(rows.mapped('kilos'))
            if not kilos:
                kilos = sum(move.product_uom._compute_quantity(
                    move.quantity or (move.product_uom_qty if picking.state != 'done' else 0), kg, round=False)
                    for move in moves if move.product_uom.category_id == kg.category_id)
            picking.step_reception_product_ids = products
            picking.step_reception_packaging_ids = packaging
            picking.step_reception_container_qty = containers
            picking.step_reception_net_kg = kilos
            picking.step_reception_avg_kg = kilos / containers if containers else 0


class Production(models.Model):
    _inherit = 'step.packing.production'

    # Converted Studio values remain native, read-only historical evidence.
    step_legacy_packing_partner_id = fields.Many2one('res.partner', string='Packing del prototipo', readonly=True)
    step_legacy_process_date = fields.Date(string='Fecha del prototipo', readonly=True)
    step_previous_process_date = fields.Date(string='Fecha nativa anterior', readonly=True)

    @api.onchange('fruit_grower_id', 'company_id')
    def _onchange_producer_fundo(self):
        for production in self:
            fundos = self.env['step.fundo'].search([
                ('partner_id', '=', production.fruit_grower_id.id),
                ('company_id', 'in', [False, production.company_id.id]),
            ], order='id') if production.fruit_grower_id else self.env['step.fundo']
            if production.fruit_fundo_id not in fundos:
                production.fruit_fundo_id = fundos[:1]


class TagLine(models.Model):
    _inherit = 'step.packing.picking.tag.line'

    step_fruit_gassed = fields.Selection([('yes', 'Sí'), ('no', 'No')], string='Fruta gasificada')
    step_fruit_chilled = fields.Selection([('yes', 'Sí'), ('no', 'No')], string='Fruta con frío')
    step_fruit_palletized = fields.Selection([('yes', 'Sí'), ('no', 'No')], string='Fruta paletizada')
    step_legacy_kg_per_box = fields.Float(string='Kg por caja del prototipo', readonly=True)


class Package(models.Model):
    _inherit = 'stock.quant.package'

    step_reception_tag_line_ids = fields.One2many(
        'step.packing.picking.tag.line', 'package_id', string='Recepciones de la tarja', readonly=True)
    # Same existing field; make incoming origins available for grouping too.
    step_packing_partner_id = fields.Many2one(
        'res.partner', related=False, compute='_compute_report_packing', store=True, string='Packing')

    @api.depends('step_packing_production_id.packing_partner_id',
                 'step_process_reception_id.step_receiving_packing_id',
                 'step_reception_tag_line_ids.picking_id.step_receiving_packing_id',
                 'step_reception_tag_line_ids.picking_id.state')
    def _compute_report_packing(self):
        for package in self:
            if package.step_packing_production_id:
                package.step_packing_partner_id = package.step_packing_production_id.packing_partner_id
            else:
                receipts = package.step_reception_tag_line_ids.picking_id.filtered(lambda p: p.state != 'cancel')
                plants = (receipts | package.step_process_reception_id).mapped('step_receiving_packing_id')
                package.step_packing_partner_id = plants if len(plants) == 1 else False


class Quant(models.Model):
    _inherit = 'stock.quant'

    @api.model
    def action_steps_packing_stock(self, category):
        labels = {'fruit': ['1 fruta'], 'materials': ['6 materiales de embalaje','6 materiales de embalajes']}.get(category)
        if not labels:
            raise UserError(_('Categoría de informe desconocida.'))
        root = self.env['product.category'].search(expression.OR([[('name','=ilike',name)] for name in labels]))
        if len(root) != 1:
            raise UserError(_('El informe requiere una categoría única «%s» en el maestro existente.', ' / '.join(labels)))
        return {
            'type': 'ir.actions.act_window', 'name': _('Stock: %s', root.display_name),
            'res_model': 'stock.quant', 'view_mode': 'list,pivot',
            'views': [(self.env.ref('step_packing_ticket_revision.stock_list').id, 'list'),
                      (self.env.ref('step_packing_ticket_revision.stock_pivot').id, 'pivot')],
            'search_view_id': self.env.ref('step_packing_ticket_revision.stock_search').id,
            'domain': [('product_id.categ_id', 'child_of', root.id), ('location_id.usage', '=', 'internal')],
            'context': {},
        }
