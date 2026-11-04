from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


GUARD = object()


class Package(models.Model):
    _inherit = 'stock.quant.package'

    step_packing_folio_key = fields.Char(readonly=True, copy=False)
    step_packing_detached_duplicate = fields.Boolean(
        compute='_compute_packing_detached_duplicate', search='_search_packing_detached_duplicate',
    )

    _sql_constraints = [
        ('step_packing_folio_key_unique', 'unique(step_packing_folio_key)',
         'Ya existe una tarja con ese folio en la compañía de Packing.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        if any('step_packing_folio_key' in vals for vals in vals_list):
            raise ValidationError(_('El folio de Packing se controla automáticamente.'))
        tags = super().create(vals_list)
        tags._sync_packing_folio()
        return tags

    def write(self, vals):
        if 'step_packing_folio_key' in vals and self.env.context.get('_packing_folio_guard') is not GUARD:
            raise ValidationError(_('El folio de Packing se controla automáticamente.'))
        reactivated = self.filtered(lambda tag: tag.step_tag_state == 'void') if 'step_tag_state' in vals else self.browse()
        result = super().write(vals)
        if {'name', 'step_packing_production_id', 'step_tag_kind', 'is_fruit_tag'} & vals.keys():
            self._sync_packing_folio()
        elif 'step_tag_state' in vals:
            (self.filtered('step_packing_folio_key') | reactivated)._sync_packing_folio()
        return result

    def _sync_packing_folio(self):
        fields_to_flush = ['name', 'step_packing_production_id', 'company_id', 'is_fruit_tag',
                           'step_tag_kind', 'step_tag_state']
        self.flush_model(fields_to_flush)
        for tag in self:
            order = tag.step_packing_production_id
            key = False
            if tag.is_fruit_tag and order and tag.step_tag_kind in ('E', 'N') and tag.step_tag_state != 'void':
                folio = (tag.name or '').strip().lower()
                if not folio:
                    raise ValidationError(_('Indique el folio de la tarja de Packing.'))
                key = f'{order.company_id.id}:{folio}'
                # Old tags retain their records. Check them as well as the
                # newly guarded records covered by the database constraint.
                if key != tag.step_packing_folio_key:
                    self.env.cr.execute("""
                        SELECT 1
                          FROM stock_quant_package p
                     LEFT JOIN step_packing_production ot ON ot.id = p.step_packing_production_id
                         WHERE p.id != %s AND p.is_fruit_tag AND p.step_tag_kind IN ('E', 'N')
                           AND p.step_tag_state IS DISTINCT FROM 'void'
                           AND COALESCE(ot.company_id, p.company_id) = %s
                           AND lower(btrim(p.name)) = %s
                         LIMIT 1
                    """, (tag.id, order.company_id.id, folio))
                    if self.env.cr.fetchone():
                        raise ValidationError(_('Ya existe una tarja con el folio %s en la compañía de Packing.') % tag.name)
            if key != tag.step_packing_folio_key:
                tag.with_context(_packing_folio_guard=GUARD).write({'step_packing_folio_key': key})

    @staticmethod
    def _packing_detail_signature(tag):
        return sorted((line.producer_id.id, line.product_id.id, line.lot_id.id or 0,
                       line.quantity, line.boxes, line.kilos) for line in tag.step_tag_line_ids)

    def _packing_detached_duplicates(self):
        candidates = self.filtered(lambda tag:
            tag.is_fruit_tag and tag.step_tag_kind in ('E', 'N') and tag.step_tag_state == 'created'
            and tag.step_packing_production_id and tag not in tag.step_packing_production_id.step_packing_output_tag_ids
            and not tag.quant_ids and not tag.step_export_shipment_ids and not tag.step_reserved_ids)
        history = self.env['stock.move.line'].sudo().search([
            '|', ('package_id', 'in', candidates.ids), ('result_package_id', 'in', candidates.ids),
        ])
        candidates -= (history.package_id | history.result_package_id)
        inspections = self.env['step.packing.inspection'].sudo().search([('package_ids', 'in', candidates.ids)])
        candidates -= inspections.package_ids
        return candidates.filtered(lambda tag: any(
            (peer.name or '').strip().lower() == (tag.name or '').strip().lower()
            and peer.step_tag_kind == tag.step_tag_kind and peer.step_tag_state != 'void'
            and peer.variedad_id == tag.variedad_id
            and self._packing_detail_signature(peer) == self._packing_detail_signature(tag)
            for peer in tag.step_packing_production_id.step_packing_output_tag_ids))

    def _compute_packing_detached_duplicate(self):
        duplicates = self.sudo()._packing_detached_duplicates()
        for tag in self:
            tag.step_packing_detached_duplicate = tag.id in duplicates.ids

    @api.model
    def _search_packing_detached_duplicate(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            raise NotImplementedError('Only boolean comparisons are supported.')
        candidates = self.sudo().search([
            ('is_fruit_tag', '=', True), ('step_tag_kind', 'in', ['E', 'N']),
            ('step_tag_state', '=', 'created'),
            ('step_packing_production_id.company_id', 'in', self.env.companies.ids),
        ])
        duplicates = candidates._packing_detached_duplicates()
        return [('id', 'in' if (operator == '=') == value else 'not in', duplicates.ids)]
