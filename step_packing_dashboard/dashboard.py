from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PackingDashboard(models.Model):
    _inherit = 'step.packing.order'

    def _dashboard_day(self, value):
        return fields.Datetime.context_timestamp(self, value).date() if value else False

    @api.model
    def get_dashboard_data(self, period='season', date_from=None, date_to=None, species_id=None):
        """Read native records in the active company; never manufacture stock totals.

        Flows use their business event date. Stock is the current validated stock
        of tags originating in the selected period (not a reconstructed ledger).
        Repacking creates new identifiers, not a second receipt or production.
        """
        if period not in ('day', 'week', 'month', 'season', 'custom'):
            raise ValidationError(_('Seleccione un período válido.'))
        try:
            species_id = int(species_id or 0)
            start, end = fields.Date.to_date(date_from), fields.Date.to_date(date_to)
        except (ValueError, TypeError):
            raise ValidationError(_('Seleccione fechas y especie válidas.'))
        if period == 'custom' and (not start or not end or start > end):
            raise ValidationError(_('Indique Desde y Hasta; Desde no puede ser posterior a Hasta.'))
        company = self.env.company
        company_domain = [('company_id', '=', company.id)]
        tags = self.env['stock.quant.package'].search(company_domain + [
            ('is_fruit_tag', '=', True), ('step_tag_kind', 'in', ['C', 'E']),
            ('step_tag_state', 'not in', ['created', 'void'])])
        productions = self.env['step.packing.production'].search(company_domain, order='id desc')
        orders = self.search(company_domain, order='id desc')
        repack_lines = self.env['step.packing.repack.line'].search([
            ('repack_id.company_id', '=', company.id), ('repack_id.state', '=', 'done')])
        parents = {}
        for line in repack_lines:
            parents.setdefault(line.target_package_id.id, set()).add(line.source_package_id.id)
        tag_by_id = {tag.id: tag for tag in tags}
        origin_dates = {}

        def origin_day(tag, visiting=None):
            if tag.id in origin_dates:
                return origin_dates[tag.id]
            visiting = set(visiting or ())
            if tag.id in visiting:
                return False
            visiting.add(tag.id)
            days = [origin_day(tag_by_id[parent], visiting) for parent in parents.get(tag.id, ())
                    if parent in tag_by_id]
            days = [day for day in days if day]
            if days:
                day = min(days)
            elif tag.step_tag_kind == 'E' and tag.step_packing_production_id:
                day = tag.step_packing_production_id.date
            else:
                receipt = tag.step_process_reception_id
                day = self._dashboard_day(receipt.date_done if receipt.state == 'done' else False)
                day = day or self._dashboard_day(tag.received_at) or self._dashboard_day(tag.create_date)
            origin_dates[tag.id] = day
            return day

        for tag in tags:
            origin_day(tag)
        today = fields.Date.context_today(self)
        known_days = [day for day in [*origin_dates.values(), *productions.mapped('date')] if day and day <= today]
        anchor = max(known_days, default=today)
        season = self.env['step.temporada'].search([
            ('company_ids', 'in', company.ids), ('start_date', '<=', anchor), ('end_date', '>=', anchor)],
            order='start_date desc, id desc', limit=1)
        if not season:
            season = self.env['step.temporada'].search([
                ('company_ids', '=', False), ('start_date', '<=', anchor), ('end_date', '>=', anchor)],
                order='start_date desc, id desc', limit=1)
        if period == 'day':
            start = end = anchor
        elif period == 'week':
            start = anchor - timedelta(days=anchor.weekday())
            end = start + timedelta(days=6)
        elif period == 'month':
            start, end = fields.Date.start_of(anchor, 'month'), fields.Date.end_of(anchor, 'month')
        elif period == 'season':
            start, end = (season.start_date, season.end_date) if season else (None, None)

        def selected_day(day):
            return bool(day and start and end and start <= day <= end)

        def selected_tag(tag):
            return not species_id or tag.especie_id.id == species_id

        species = (tags.especie_id | productions.fruit_species_id | orders.line_ids.species_id).sorted('name')
        if species_id and species_id not in species.ids:
            # Do not accept inaccessible company/species combinations from RPC.
            raise ValidationError(_('La especie no tiene registros visibles en esta empresa.'))
        selected_productions = productions.filtered(lambda p: selected_day(p.date)
            and (not species_id or p.fruit_species_id.id == species_id
                 or species_id in p.step_packing_input_tag_ids.especie_id.ids))
        selected_orders = orders.filtered(lambda p: selected_day(p.week_start)
            and (not species_id or species_id in p.line_ids.species_id.ids))
        cohort = tags.filtered(lambda t: selected_tag(t) and selected_day(origin_dates[t.id]))
        roots = cohort.filtered(lambda t: t.id not in parents)
        received = roots.filtered(lambda t: t.step_tag_kind == 'C')
        exported = roots.filtered(lambda t: t.step_tag_kind == 'E')
        process_tags = selected_productions.filtered(
            lambda p: p.state in ('closed', 'costed', 'accounted')).step_packing_input_tag_ids
        processed = (tags & process_tags).filtered(lambda t: t.step_tag_kind == 'C'
            and t.step_tag_state == 'processed' and selected_tag(t))
        stock_c = cohort.filtered(lambda t: t.step_tag_kind == 'C' and t.step_tag_state == 'validated')
        stock_e = cohort.filtered(lambda t: t.step_tag_kind == 'E' and t.step_tag_state == 'validated')
        # Shipment date comes from completed native stock movements; a later
        # liquidation or document edit must not move the shipment into a new day.
        dispatched = tags.filtered(lambda t: t.step_tag_kind == 'E'
            and t.step_tag_state in ('dispatched', 'liquidated') and selected_tag(t))
        moves = self.env['stock.move.line'].search(company_domain + [
            ('package_id', 'in', dispatched.ids), ('state', '=', 'done'),
            ('location_dest_id.usage', '=', 'customer')]) if dispatched else self.env['stock.move.line']
        dispatch_days = {}
        for move in moves:
            day = self._dashboard_day(move.date)
            dispatch_days[move.package_id.id] = max(day, dispatch_days.get(move.package_id.id, day))
        for tag in dispatched:
            if tag.id not in dispatch_days:
                shipments = tag.step_export_shipment_ids.filtered(
                    lambda s: s.company_id == company and s.state in ('dispatched', 'shipped', 'invoiced', 'settled'))
                dates = [day for day in shipments.mapped('date') if day]
                if dates:
                    dispatch_days[tag.id] = max(dates)
        shipped = dispatched.filtered(lambda t: selected_day(dispatch_days.get(t.id)))
        open_productions = selected_productions.filtered(lambda p: p.state in ('created', 'validated'))
        to_close = open_productions.filtered(lambda p: p.state == 'validated')
        to_validate = open_productions.filtered(lambda p: p.state == 'created')
        groups = {'received_kg': received, 'processed_kg': processed, 'stock_input_kg': stock_c,
                  'export_kg': exported, 'shipped_kg': shipped, 'stock_export_kg': stock_e}
        kpis = {key: sum(records.mapped('step_actual_kg')) for key, records in groups.items()}
        kpis['open_productions'] = len(open_productions)
        # Retain keys consumed by previous clients while replacing their UI.
        kpis['open_orders'] = len(selected_orders.filtered(lambda p: p.state in ('draft', 'validated')))
        kpis['input_kg'] = kpis['received_kg']
        actions = {key: {'type': 'ir.actions.act_window', 'name': _('Tarjas de Packing'),
                        'res_model': 'stock.quant.package', 'view_mode': 'list,form',
                        'domain': [('id', 'in', records.ids)]} for key, records in groups.items()}
        actions['open_productions'] = {'type': 'ir.actions.act_window', 'name': _('OT abiertas'),
            'res_model': 'step.packing.production', 'view_mode': 'list,form',
            'domain': [('id', 'in', open_productions.ids)]}
        return {
            'company_name': company.display_name, 'kpis': kpis, 'actions': actions,
            'filters': {'period': period, 'date_from': fields.Date.to_string(start) or '',
                        'date_to': fields.Date.to_string(end) or '', 'species_id': species_id or ''},
            'species': [{'id': s.id, 'name': s.display_name} for s in species],
            'period_label': season.display_name if period == 'season' and season else '',
            'notice': _('No hay temporada con fechas para el último día con actividad. Seleccione un rango de fechas.')
                if period == 'season' and not season else '',
            'undated_shipments': len(dispatched.filtered(lambda t: t.id not in dispatch_days)),
            'attention': {
                'orders_without_materials': len(selected_orders.filtered(lambda p: p.state == 'validated' and not p.material_need_ids)),
                'productions_to_close': len(to_close), 'productions_to_validate': len(to_validate)},
            'recent_orders': [{'id': p.id, 'name': p.name, 'state': p.state,
                'state_label': dict(p._fields['state'].selection).get(p.state),
                'boxes': p.planned_boxes, 'kg': p.planned_kg} for p in selected_orders[:6]],
            'recent_productions': [{'id': p.id, 'name': p.name, 'state': p.state,
                'state_label': dict(p._fields['state'].selection).get(p.state),
                'order': p.step_packing_order_id.name or '', 'product': p.product_id.display_name or '',
                'input_kg': p.step_packing_input_kg} for p in selected_productions[:6]],
        }
