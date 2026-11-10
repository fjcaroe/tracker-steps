"""Check the physical sources of fruit advances, including split input tags."""
from odoo import _, models
from odoo.exceptions import ValidationError
from odoo.osv import expression


BASIS = [('processed', 'Kilos procesados'), ('received', 'Kilos recibidos')]


def lock_companies(companies):
    if not companies:
        return
    # A write to the same row makes a competing stale Repeatable Read
    # transaction retry, even if its proforma would use different C/E tags.
    # Keep the company's audit fields and business values unchanged.
    companies.env.cr.execute("""
        SELECT id FROM res_company WHERE id = ANY(%s) ORDER BY id FOR NO KEY UPDATE
    """, [companies.ids])
    companies.env.cr.execute("""
        UPDATE res_company SET write_date = write_date WHERE id = ANY(%s)
    """, [companies.ids])


def source_rows(order):
    return [row for line in order.order_line for row in (line.step_fruit_source_rows or [])]


def source_key(row):
    return (row['tag_line_id'], row.get('input_tag_id') or 0, row['receipt_id'])


class Package(models.Model):
    _inherit = 'stock.quant.package'

    def _advance_raw_descendants(self, company):
        seen, frontier = self, self
        while frontier:
            children = self.env['step.fruit.package.line'].search([
                ('source_package_id', 'in', frontier.ids), ('package_id.step_tag_kind', '=', 'C'),
                ('package_id.company_id', 'in', [False, company.id]),
            ]).package_id
            frontier = children - seen
            seen |= frontier
        return seen

    def _advance_root_map(self, company):
        memo = {}

        def roots(tag, ancestors):
            if tag.id in ancestors:
                raise ValidationError(_('La trazabilidad de la tarja contiene un ciclo.'))
            if tag.id not in memo:
                parents = tag.step_tag_line_ids.source_package_id.filtered(
                    lambda parent: parent.step_tag_kind == 'C' and (
                        not parent.company_id or parent.company_id == company))
                # An empty company can occur after the original stock is used.
                memo[tag.id] = (set().union(*(roots(parent, ancestors | {tag.id}) for parent in parents))
                                if parents else {tag.id})
            return memo[tag.id]

        for tag in self.filtered(lambda package: package.step_tag_kind == 'C'):
            roots(tag, set())
        return memo


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def _advance_candidates(self, company, rows):
        tags = list({row['tag_id'] for row in rows})
        receipts = list({row['receipt_id'] for row in rows})
        return self.sudo().search(expression.AND([
            [('company_id', '=', company.id), ('step_fruit_proforma', '=', True),
             ('step_fruit_state', '!=', 'cancel')],
            expression.OR([[('step_fruit_tag_ids', 'in', tags)], [
                ('step_advance_proforma', '=', True), ('step_fruit_receipt_ids', 'in', receipts)]]),
        ]))

    def _advance_monthly_raw_roots(self, company, raw_ids):
        packages = self.env['stock.quant.package'].sudo()
        if not raw_ids:
            return set()
        descendants = packages.browse(sorted(raw_ids))._advance_raw_descendants(company)
        ots = self.env['step.packing.production'].sudo().search([
            ('company_id', '=', company.id), ('state', 'in', ('closed', 'costed', 'accounted')),
            ('step_packing_input_tag_ids', 'in', descendants.ids),
        ])
        monthly = self.sudo().search([
            ('company_id', '=', company.id), ('step_fruit_proforma', '=', True),
            ('step_advance_proforma', '=', False), ('step_fruit_state', '!=', 'cancel'),
            ('step_fruit_production_ids', 'in', ots.ids),
        ])
        billed = ots.filtered(lambda ot: ot.purchase_bill_id and ot.purchase_bill_id.state != 'cancel')
        inputs = ((monthly.step_fruit_production_ids & ots) | billed).step_packing_input_tag_ids
        return set().union(*inputs._advance_root_map(company).values())

    def _advance_reservations(self, company, basis, rows, exclude=None):
        """Return exact reservations and whole tags/origins already committed."""
        candidates = self._advance_candidates(company, rows)
        if exclude:
            candidates -= exclude.sudo()
        advances = candidates.filtered('step_advance_proforma')
        existing_rows = [(order, row) for order in advances for row in source_rows(order)]
        packages = self.env['stock.quant.package'].sudo()
        origin_ids = {row.get('input_tag_id') or row['tag_id']
                      for row in [*rows, *(row for _order, row in existing_rows)]}
        origins = packages.browse(sorted(origin_ids)).exists()._advance_root_map(company)
        exact = {source_key(row): order.id for order, row in existing_rows}
        tags = set(candidates.filtered(lambda order: not order.step_advance_proforma
            or order.step_fruit_state in ('approved', 'invoiced')).step_fruit_tag_ids.ids)
        cross_basis = set()
        for order, row in existing_rows:
            if (order.step_advance_basis or 'processed') != basis:
                tags.add(row['tag_id'])
                cross_basis.update(origins.get(row.get('input_tag_id') or row['tag_id'], ()))
        if basis == 'received':
            received = set().union(*(origins.get(row['tag_id'], set()) for row in rows))
            cross_basis.update(self._advance_monthly_raw_roots(company, received))
        return exact, tags, cross_basis, origins

    def _advance_check_monthly_inputs(self, company, productions):
        inputs = productions.sudo().step_packing_input_tag_ids
        roots = set().union(*inputs._advance_root_map(company).values())
        if roots and self.sudo().search_count([
                ('company_id', '=', company.id), ('step_advance_proforma', '=', True),
                ('step_advance_basis', '=', 'received'), ('step_fruit_state', '!=', 'cancel'),
                ('step_fruit_tag_ids', 'in', sorted(roots)),
        ], limit=1):
            raise ValidationError(_('La compra mensual incluye fruta reservada en un anticipo por kilos recibidos.'))
