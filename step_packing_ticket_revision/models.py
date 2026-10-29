from odoo import api, fields, models, _
from odoo.exceptions import UserError


class Picking(models.Model):
    _inherit = 'stock.picking'

    step_receiving_packing_id = fields.Many2one(
        'res.partner', string='Packing', check_company=True,
        domain="[('step_export_packing','=',True)]")


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
        label = {'fruit': '1 fruta', 'materials': '6 materiales de embalajes'}.get(category)
        if not label:
            raise UserError(_('Categoría de informe desconocida.'))
        root = self.env['product.category'].search([('name', '=ilike', label)])
        if len(root) != 1:
            raise UserError(_('El informe requiere una categoría única «%s» en el maestro existente.', label))
        return {
            'type': 'ir.actions.act_window', 'name': _('Stock: %s', root.display_name),
            'res_model': 'stock.quant', 'view_mode': 'list,pivot',
            'views': [(self.env.ref('step_packing_ticket_revision.stock_list').id, 'list'),
                      (self.env.ref('step_packing_ticket_revision.stock_pivot').id, 'pivot')],
            'search_view_id': self.env.ref('step_packing_ticket_revision.stock_search').id,
            'domain': [('product_id.categ_id', 'child_of', root.id), ('location_id.usage', '=', 'internal')],
            'context': {},
        }
