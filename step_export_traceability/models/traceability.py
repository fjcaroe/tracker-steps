"""Read native evidence without creating a parallel traceability ledger."""
from html import escape
from html import unescape
import re
from odoo import fields, models
from odoo.tools import format_datetime, format_date


class Shipment(models.Model):
    _inherit = 'step.export.export'

    arrival_quality_id = fields.Many2one('step.management.fruit.quality', string='Calidad llegada')


class Package(models.Model):
    _inherit = 'stock.quant.package'

    trace_panel = fields.Html(compute='_compute_trace', sanitize=False, string='Panel de trazabilidad')
    trace_origin = fields.Char(compute='_compute_trace', string='Productor / origen')
    trace_reception = fields.Char(compute='_compute_trace', string='Recepción')
    trace_process = fields.Char(compute='_compute_trace', string='Embalado / proceso')
    trace_quality = fields.Char(compute='_compute_trace', string='Calidad / SAG')
    trace_dispatch = fields.Char(compute='_compute_trace', string='Despacho')
    trace_export = fields.Char(compute='_compute_trace', string='Exportación')
    trace_receiver = fields.Char(compute='_compute_trace', string='Recibidor / llegada')

    def _trace_search(self, model, domain):
        """ACLs and record rules remain effective, including for linked evidence."""
        target = self.env[model]
        if not target.has_access('read'):
            return target.browse()
        if 'company_id' in target._fields:
            domain = [*domain, ('company_id', 'in', self.env.companies.ids + [False])]
        elif model == 'step.packing.repack.line':
            # Legacy lines have no company rule of their own. Scope through
            # their parent even when an emptied source package is now shared.
            domain = [*domain, ('repack_id.company_id', 'in', self.env.companies.ids)]
        return target.search(domain)

    def _trace_graph(self):
        self.ensure_one()
        self.check_access('read')
        tags = self
        productions = self.env['step.packing.production'].browse()
        repacks = self.env['step.packing.repack'].browse()
        frontier = self
        # Follow validated repalletization and native OT inputs backwards;
        # visited IDs bound cycles without dropping older lineage arbitrarily.
        while frontier:
            ots = self._trace_search('step.packing.production', [
                ('step_packing_output_tag_ids', 'in', frontier.ids)])
            lines = self._trace_search('step.packing.repack.line', [
                ('target_package_id', 'in', frontier.ids), ('repack_id.state', '=', 'done')])
            productions |= ots
            repacks |= lines.repack_id
            parents = ots.step_packing_input_tag_ids | lines.source_package_id | frontier.step_tag_line_ids.source_package_id
            # Never bypass package rules through a related record's relation.
            visible = self._trace_search('stock.quant.package', [('id', 'in', parents.ids)])
            frontier = visible - tags
            tags |= frontier
        receipts = self._trace_search('stock.picking', [
            ('fruit_tag_line_ids.package_id', 'in', tags.ids),
            ('picking_type_code', '=', 'incoming'), ('state', '!=', 'cancel')])
        moves = self._trace_search('stock.move.line', [
            ('result_package_id', 'in', tags.ids), ('picking_id.picking_type_code', '=', 'incoming'),
            ('state', '=', 'done')])
        receipts |= moves.picking_id
        inspections = self._trace_search('step.packing.inspection', [('package_ids', 'in', tags.ids)])
        checks = self._trace_search('quality.check', [
            '|', ('picking_id', 'in', receipts.ids), ('move_line_id.result_package_id', 'in', tags.ids)])
        guides = self._trace_search('step.dispatch.guide', [
            '|', ('load_tag_ids', 'in', self.ids), ('id', 'in', self.step_guide_ids.ids)])
        shipments = self._trace_search('step.export.export', [('tag_ids', 'in', self.ids)])
        shipment_guides = self._trace_search('step.dispatch.guide', [
            ('id', 'in', shipments.dispatch_guide_ids.ids)]) - guides
        claims = self._trace_search('step.export.customer.claim', [
            '|', ('tag_ids', 'in', self.ids), ('line_ids.tag_id', 'in', self.ids)])
        return dict(tags=tags, productions=productions, repacks=repacks, receipts=receipts,
                    checks=checks, inspections=inspections, guides=guides, shipment_guides=shipment_guides,
                    shipments=shipments, claims=claims)

    def _compute_trace(self):
        def text(value):
            return escape(str(value)) if value is not False and value is not None and value != '' else 'Sin registro'

        def value(records, field):
            vals = records.mapped(field)
            if hasattr(vals, '_name'):
                return links(vals)
            if records._fields[field].type == 'datetime':
                vals = [format_datetime(self.env, v) for v in vals if v]
            elif records._fields[field].type == 'date':
                vals = [format_date(self.env, v) for v in vals if v]
            return text(' · '.join(dict.fromkeys(str(v) for v in vals if v is not False and v is not None and v != '')))

        def links(records):
            return ' · '.join('<a href="/web#id=%s&amp;model=%s&amp;view_type=form">%s</a>' %
                             (r.id, escape(r._name, quote=True), text(r.display_name)) for r in records) or 'Sin registro'

        def choices(records, field):
            return text(' · '.join(dict.fromkeys(dict(r._fields[field]._description_selection(r.env)).get(r[field], '')
                                                for r in records if r[field])))

        for tag in self:
            g = tag._trace_graph()
            origins, receipts, ots = g['tags'], g['receipts'], g['productions']
            inspections, checks, guides, ships, claims = (g[k] for k in ('inspections', 'checks', 'guides', 'shipments', 'claims'))
            receipt_checks = checks.filtered(lambda c: c.picking_id in receipts)
            internal = inspections.filtered(lambda i: i.kind == 'internal')
            sag = inspections.filtered(lambda i: i.kind == 'sag')
            producers = origins.step_tag_line_ids.producer_id | origins.step_producer_id
            sections = [
                ('Productor', [('Productor', links(producers)), ('Fundo', value(origins, 'fundo_id')),
                 ('Cuartel registrado en recepción', value(receipts, 'step_fruit_cost_center')),
                 ('Especie', value(tag, 'especie_id')), ('Variedad', value(tag, 'variedad_id')),
                 ('Fecha cosecha', value(origins, 'harvest_date')), ('Guía productor', value(receipts, 'fruit_guide_number'))]),
                ('Recepción', [('Fecha recepción', value(receipts, 'date_done')), ('Número recepción', links(receipts)),
                 ('Lote', value(receipts, 'fruit_lot')), ('Lotes de stock', value(moves_for(origins, receipts), 'lot_id')),
                 ('Tipo fruta', choices(origins, 'fruit_type')), ('Folio calidad', links(receipt_checks)),
                 ('Calificación', choices(receipt_checks, 'quality_state'))]),
                ('Embalado', [('Fecha proceso', value(ots, 'date')), ('Número proceso / OT', links(ots)),
                 ('Repaletizajes', links(g['repacks'])), ('Tarjas de origen', links(origins - tag)),
                 ('Calibre', value(tag, 'fruit_caliber_id')), ('Embalaje', value(tag, 'step_packaging_id')),
                 ('Cajas', text(tag.step_actual_boxes if tag.step_tag_line_ids else tag.box_count)),
                 ('Kilos', text(tag.step_actual_kg if tag.step_tag_line_ids else tag.kilos_total))]),
                ('Calidad', [('Fecha calidad', value(internal, 'date')), ('Folio calidad', links(internal)),
                 ('Calificación', choices(internal, 'state')), ('Calidad fruta', value(tag, 'fruit_quality_id')),
                 ('Folio SAG / SIF', value(sag, 'sag_sif_reference')), ('Lote SAG', links(sag)),
                 ('Fecha SAG', value(sag, 'date')), ('Resultado SAG', choices(sag, 'state'))]),
                ('Despacho', [('Fecha despacho', value(guides, 'departure_datetime')), ('Guía despacho', links(guides)),
                 ('Folio guía', value(guides, 'external_folio')), ('Fecha guía', value(guides, 'date')),
                 ('Contenedor', value(ships, 'container_reference')),
                 ('Transportista', value(guides, 'carrier_id')), ('Camión', value(guides, 'vehicle_id')),
                 ('Patente registrada', value(guides, 'truck_plate')), ('Instructivo despacho', value(guides, 'dispatch_instruction_id')),
                 ('Guías del embarque sin asignación individual', links(g['shipment_guides'])),
                 ('Fecha de esas guías', value(g['shipment_guides'], 'date')),
                 ('Transportista de esas guías', value(g['shipment_guides'], 'carrier_id')),
                 ('Patente de esas guías', value(g['shipment_guides'], 'truck_plate'))]),
                ('Exportación', [('Número embarque', value(ships, 'shipment_number')),
                 ('Fecha zarpe', value(ships, 'departure_date')), ('Nave', value(ships, 'vessel_id')),
                 ('Recibidor', value(ships, 'receiver_id')), ('BL', value(ships, 'bl_folio')),
                 ('Proforma / folio comercial', value(ships, 'folio_sale_order_id')),
                 ('Notas de venta', value(ships, 'sale_order_ids')), ('Instructivo embarque', links(ships)),
                 ('Estado embarque', choices(ships, 'state'))]),
                ('Recibidor', [('Fecha arribo registrada', value(ships, 'arrival_date')), ('Puerto arribo', value(ships, 'destination_port_id')),
                 ('Calidad llegada', value(ships, 'arrival_quality_id')), ('Folio reclamo de esta tarja', links(claims))]),
            ]
            for field, (_, rows) in zip(('trace_origin','trace_reception','trace_process','trace_quality',
                                        'trace_dispatch','trace_export','trace_receiver'), sections):
                tag[field] = ' | '.join(label + ': ' + unescape(re.sub('<[^>]*>', '', val)) for label, val in rows)
            tag.trace_panel = '<div class="o_step_trace_grid">' + ''.join(
                '<section><h3>%s</h3><dl>%s</dl></section>' % (text(title), ''.join(
                    '<dt>%s</dt><dd>%s</dd>' % (text(label), val) for label, val in rows)) for title, rows in sections) + '</div>'


def moves_for(tag, receipts):
    return tag._trace_search('stock.move.line', [('picking_id', 'in', receipts.ids),
        ('result_package_id', 'in', tag.ids), ('state', '=', 'done')])
