"""Native inventory expense and analytic charge to the repalletization order."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from .analytics import _ORIGIN, packing_distribution


class Repack(models.Model):
    _inherit = 'step.packing.repack'

    step_analytic_season_id = fields.Many2one('step.temporada', string='Temporada para analítica')
    step_effective_season_id = fields.Many2one('step.temporada', compute='_compute_analytic_sources')
    fruit_species_id = fields.Many2one('step.especie', compute='_compute_analytic_sources')

    @api.depends('step_analytic_season_id', 'line_ids.source_package_id.step_export_season_id',
                 'line_ids.source_package_id.especie_id')
    def _compute_analytic_sources(self):
        for record in self:
            seasons = record.source_tag_ids.step_export_season_id
            species = record.source_tag_ids.especie_id
            record.step_effective_season_id = record.step_analytic_season_id or (seasons if len(seasons) == 1 else False)
            record.fruit_species_id = species if len(species) == 1 else False

    def _packing_distribution(self, create=False, existing=None):
        return packing_distribution(self, create, existing)

    def _packing_move_extra_values(self, product, qty, source, dest, lines):
        values = super()._packing_move_extra_values(product, qty, source, dest, lines)
        values.update(step_analytic_repack_id=self.id, step_packing_consumption=True)
        return values

    def _create_repack_material_move(self):
        picking = super(Repack, self.with_context(_packing_analytic_origin=_ORIGIN))._create_repack_material_move()
        # Stock users validate the operation; the native valuation boundary
        # reads and posts the resulting accounting with controlled privileges.
        for move in picking.move_ids.sudo():
            if move.account_move_ids.filtered(lambda entry: entry.state != 'cancel'):
                continue
            accounts = move.with_company(self.company_id).product_id.product_tmpl_id.get_product_accounts()
            expense, valuation, journal = accounts.get('expense'), accounts.get('stock_valuation'), accounts.get('stock_journal')
            if not expense or not valuation or not journal:
                raise UserError(_('Configure cuenta de gasto, cuenta de inventario y diario de valoración para %s.') % move.product_id.display_name)
            amount = self.company_id.currency_id.round(-sum(move.stock_valuation_layer_ids.mapped('value')))
            if amount <= 0:
                raise UserError(_('Ingrese un costo mayor a cero para contabilizar el material %s.') % move.product_id.display_name)
            distribution = self._packing_distribution(create=True)
            # This is the same controlled privilege boundary as native stock
            # valuation. Operators confirm stock, without gaining ledger access.
            entry = self.env['account.move'].sudo().with_company(self.company_id).create({
                'move_type': 'entry', 'company_id': self.company_id.id, 'journal_id': journal.id,
                'date': self.date, 'ref': self.name, 'stock_move_id': move.id,
                'line_ids': [(0, 0, {'name': move.product_id.display_name, 'account_id': expense.id,
                                    'product_id': move.product_id.id, 'debit': amount,
                                    'analytic_distribution': distribution}),
                             (0, 0, {'name': move.product_id.display_name, 'account_id': valuation.id,
                                     'product_id': move.product_id.id, 'credit': amount})],
            })
            entry.action_post()
            move.stock_valuation_layer_ids.sudo().write({'account_move_id': entry.id})
        return picking

    def write(self, vals):
        if 'step_analytic_season_id' in vals and any(r.state != 'draft' for r in self):
            raise UserError(_('La temporada analítica del repaletizado validado se conserva.'))
        return super().write(vals)
