from datetime import date, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


def ratio(numerator, denominator, percent=False):
    return numerator / denominator * (100 if percent else 1) if denominator else None


class Comparisons(models.Model):
    _inherit = 'step.packing.order'

    @api.model
    def operational_comparison(self, kind='producers', filters=None):
        if kind not in ('producers', 'packing'):
            raise ValidationError(_('Comparativo desconocido.'))
        filters = filters or {}
        try:
            season_id, species_id = (int(filters.get(key) or 0) for key in ('season_id', 'species_id'))
            month, week = filters.get('month') or '', filters.get('week') or ''
            if month:
                date.fromisoformat(month + '-01')
            if week and date.fromisoformat(week).weekday() != 0:
                raise ValueError()
        except (ValueError, TypeError):
            raise ValidationError(_('Seleccione filtros de período válidos.'))
        companies = self.env.companies.ids
        productions = self.env['step.packing.production'].search([
            ('company_id', 'in', companies), ('state', 'in', ['closed', 'costed', 'accounted'])])
        data = []
        output_ids = set(productions.mapped('step_packing_output_tag_ids').ids)
        for production in productions:
            seasons = production.step_packing_input_tag_ids.mapped('step_export_season_id')
            season = seasons if len(seasons) == 1 else production.step_packing_order_id.sales_program_id.season_id
            base = {'date': production.date, 'season': season,
                    'species': production.fruit_species_id, 'variety': production.fruit_variety_id}
            if kind == 'packing':
                data.append(dict(base, source='process', line=production.step_packing_line_id,
                    input=production.step_packing_input_kg, export=production.step_packing_export_kg,
                    commercial=production.step_packing_commercial_kg,
                    precaliber=production.step_packing_precaliber_kg, waste=production.step_packing_waste_kg,
                    loss=production.step_packing_loss_kg, hours=production.effective_hours,
                    standard=production.standard_kg_hour))
            else:
                for tag in production.step_packing_output_tag_ids.filtered(lambda t: t.step_packing_result == 'export'):
                    data.append(dict(base, source='actual', value=tag.step_actual_kg,
                        species=tag.especie_id or base['species'], variety=tag.variedad_id or base['variety'],
                        season=tag.step_export_season_id or season))
        if kind == 'producers':
            weeks = self.env['step.export.estimate.week'].search([
                ('line_id.estimate_id.company_id', 'in', companies), ('line_id.estimate_id.state', '=', 'current')])
            for row in weeks:
                data.append({'source': 'estimated', 'date': row.week_start,
                    'season': row.line_id.estimate_id.season_id, 'species': row.line_id.species_id,
                    'variety': row.line_id.variety_id, 'value': row.export_kg})
            receipts = self.env['step.packing.picking.tag.line'].search([
                ('company_id', 'in', companies), ('picking_id.state', '=', 'done'),
                ('picking_id.picking_type_id.code', '=', 'incoming'),
                ('picking_id.step_fruit_reception_kind', '=', 'packed')])
            seen = set(output_ids)
            for row in receipts:
                tag, picking = row.package_id, row.picking_id
                if not tag or tag.id in seen or tag.step_tag_kind != 'E':
                    continue
                seen.add(tag.id)
                done = fields.Datetime.context_timestamp(self, picking.date_done).date() if picking.date_done else False
                data.append({'source': 'actual', 'date': done, 'season': picking.fruit_season_id,
                    'species': picking.fruit_species_id, 'variety': picking.fruit_variety_id, 'value': row.kilos})

        seasons, species, periods = {}, {}, set()
        for row in data:
            if row['season']:
                seasons[row['season'].id] = row['season'].display_name
            if row['species']:
                species[row['species'].id] = row['species'].display_name
            if row['date']:
                periods.add(row['date'])
        def selected(row):
            day = row['date']
            return ((not season_id or row['season'].id == season_id)
                and (not species_id or row['species'].id == species_id)
                and (not month or day and day.strftime('%Y-%m') == month)
                and (not week or day and (day - timedelta(days=day.weekday())).isoformat() == week))
        rows = [row for row in data if selected(row)]
        tables = self._producer_tables(rows) if kind == 'producers' else self._packing_tables(rows)
        return {'tables': tables,
            'seasons': [{'id': key, 'name': value} for key, value in sorted(seasons.items(), key=lambda x: x[1])],
            'species': [{'id': key, 'name': value} for key, value in sorted(species.items(), key=lambda x: x[1])],
            'months': sorted({day.strftime('%Y-%m') for day in periods}),
            'weeks': [{'id': day.isoformat(), 'name': '%s-W%02d · %s' % (*day.isocalendar()[:2], day.strftime('%d/%m/%Y'))}
                for day in sorted({day-timedelta(days=day.weekday()) for day in periods})],
            'undated': sum(not row['date'] for row in data)}

    @api.model
    def _producer_tables(self, records):
        tables = []
        for detailed in (False, True):
            groups = {}
            for record in records:
                key = (record['species'].id, record['variety'].id if detailed else 0)
                row = groups.setdefault(key, {'key': str(key), 'species': record['species'].display_name or _('Sin especie'),
                    'variety': record['variety'].display_name or _('Sin variedad'), 'estimated': 0.0, 'actual': 0.0})
                row[record['source']] += record['value']
            values = sorted(groups.values(), key=lambda r: (r['species'], r['variety']))
            total = {'species': _('Totales'), 'variety': '', 'estimated': sum(r['estimated'] for r in values),
                     'actual': sum(r['actual'] for r in values)}
            for row in values + [total]:
                row['difference'] = row['actual'] - row['estimated']
                row['variation'] = ratio(row['difference'], row['estimated'], True)
            columns = [('species', 'Especie', 'text')]
            if detailed:
                columns.append(('variety', 'Variedad', 'text'))
            columns += [('estimated', 'Estimado', 'number'), ('actual', 'Real', 'number'),
                        ('difference', 'Diferencia', 'number'), ('variation', '% variación', 'percent')]
            tables.append({'key': 'variety' if detailed else 'species',
                'title': 'Kilos exportación por variedad' if detailed else 'Kilos exportación por especie',
                'columns': columns, 'rows': values, 'total': total})
        return tables

    @api.model
    def _packing_tables(self, records):
        process, machinery = {}, {}
        measures = ('input', 'export', 'commercial', 'precaliber', 'waste', 'loss')
        for record in records:
            species = record['species']
            row = process.setdefault(species.id, dict(key=str(species.id), species=species.display_name or _('Sin especie'),
                **{key: 0.0 for key in measures}))
            for key in measures:
                row[key] += record[key]
            key = (species.id, record['line'].id)
            machine = machinery.setdefault(key, {'key': str(key), 'species': species.display_name or _('Sin especie'),
                'line': record['line'].display_name or _('Sin línea'), 'input': 0.0, 'hours': 0.0,
                'standard_capacity': 0.0, 'standard_hours': 0.0, 'missing_hours': 0})
            if record['hours'] > 0:
                machine['input'] += record['input']; machine['hours'] += record['hours']
                if record['standard'] > 0:
                    machine['standard_capacity'] += record['standard'] * record['hours']
                    machine['standard_hours'] += record['hours']
            else:
                machine['missing_hours'] += 1
        process_rows = sorted(process.values(), key=lambda r: r['species'])
        total = dict(species=_('Totales'), **{key: sum(r[key] for r in process_rows) for key in measures})
        for row in process_rows + [total]:
            row['export_percent'] = ratio(row['export'], row['input'], True)
            row['loss_percent'] = ratio(row['loss'], row['input'], True)
        machine_rows = sorted(machinery.values(), key=lambda r: (r['species'], r['line']))
        machine_total = dict(species=_('Totales'), line='', **{key: sum(r[key] for r in machine_rows)
            for key in ('input', 'hours', 'standard_capacity', 'standard_hours', 'missing_hours')})
        for row in machine_rows + [machine_total]:
            row['actual_rate'] = ratio(row['input'], row['hours'])
            # A partially configured baseline must not look like a complete standard.
            row['standard_rate'] = ratio(row['standard_capacity'], row['hours']) if row['hours'] == row['standard_hours'] else None
            row['variation'] = (row['actual_rate'] / row['standard_rate'] - 1) * 100 if row['standard_rate'] else None
        return [
            {'key': 'process', 'title': 'Resultado de procesos', 'rows': process_rows, 'total': total,
             'columns': [('species', 'Especie', 'text'), ('input', 'Kg a proceso', 'number'),
                ('export', 'Kg exportación', 'number'), ('commercial', 'Comercial', 'number'),
                ('precaliber', 'Precalibre', 'number'), ('waste', 'Desecho', 'number'), ('loss', 'Merma', 'number'),
                ('export_percent', '% exportación', 'percent'), ('loss_percent', '% merma', 'percent')]},
            {'key': 'machinery', 'title': 'Rendimiento de maquinaria', 'rows': machine_rows, 'total': machine_total,
             'columns': [('species', 'Especie', 'text'), ('line', 'Línea', 'text'), ('input', 'Kg procesados', 'number'),
                ('hours', 'Horas efectivas', 'number'), ('actual_rate', 'Kg/h real', 'number'),
                ('standard_rate', 'Kg/h estándar', 'number'), ('variation', '% variación', 'percent'),
                ('missing_hours', 'OT sin horas', 'number')]},
        ]
