"""Read-only T96 comparisons over existing sales programmes and shipments."""
from datetime import date, timedelta
from odoo import api, models, _
from odoo.exceptions import ValidationError


class ExportDashboard(models.Model):
    _inherit = 'step.export.sales.program'

    @api.model
    def dashboard_comparison(self, filters=None):
        filters = filters or {}
        season_id = int(filters.get('season_id') or 0)
        month = filters.get('month') or ''
        week = filters.get('week') or ''
        try:
            if month:
                date.fromisoformat(month + '-01')
            if week and date.fromisoformat(week).weekday() != 0:
                raise ValueError()
        except (ValueError, TypeError):
            raise ValidationError(_('Seleccione un mes válido y una semana que comience el lunes.'))
        companies = self.env.companies.ids
        programs = self.search([('company_id', 'in', companies), ('state', '=', 'current')])
        shipments = self.env['step.export.export'].search([
            ('company_id', 'in', companies), ('state', 'in', ['shipped', 'invoiced', 'settled'])])
        seasons = (programs.mapped('season_id') | shipments.mapped('season_id')).sorted('name')
        periods = set(programs.mapped('line_ids.week_start'))
        periods.update(shipments.mapped('date'))
        periods.discard(False)
        months = sorted({day.strftime('%Y-%m') for day in periods})
        weeks = sorted({day - timedelta(days=day.weekday()) for day in periods})

        def selected(day, season):
            return (not season_id or season.id == season_id) and (
                not month or day and day.strftime('%Y-%m') == month) and (
                not week or day and (day - timedelta(days=day.weekday())).isoformat() == week)

        species_rows, program_rows = {}, {}

        def rows(program, species, company):
            species_key = species.id or 0
            program_key = '%s:%s' % (company.id, program.series_code) if program else 'unassigned'
            if species_key not in species_rows:
                species_rows[species_key] = self._dashboard_row(str(species_key), species.display_name or _('Sin especie'))
            if program_key not in program_rows:
                name = '%s · %s' % (program.series_code, program.name) if program else _('Sin programa')
                if len(companies) > 1 and program:
                    name += ' · ' + company.display_name
                program_rows[program_key] = self._dashboard_row(program_key, name)
            return species_rows[species_key], program_rows[program_key]

        for program in programs:
            for line in program.line_ids:
                if selected(line.week_start, program.season_id):
                    for row in rows(program, program.species_id, program.company_id):
                        row['planned_kg'] += line.kg_qty
                        row['planned_usd'] += line.amount_usd
        undated = 0
        for shipment in shipments:
            if not shipment.date:
                undated += 1
            if selected(shipment.date, shipment.season_id):
                for row in rows(shipment.sales_program_id, shipment.species_id, shipment.company_id):
                    row['actual_kg'] += shipment.kg_qty

        def finish(items):
            values = sorted(items.values(), key=lambda item: item['name'])
            total = self._dashboard_row('total', _('Totales'))
            for row in values:
                for key in ('planned_kg', 'planned_usd', 'actual_kg'):
                    total[key] += row[key]
            for row in values + [total]:
                row['planned_price'] = row['planned_usd'] / row['planned_kg'] if row['planned_kg'] else None
            return {'rows': values, 'total': total}

        return {
            'species': finish(species_rows), 'programs': finish(program_rows),
            'seasons': [{'id': season.id, 'name': season.display_name} for season in seasons],
            'months': months,
            'weeks': [{'id': day.isoformat(), 'name': '%s-W%02d · %s' % (*day.isocalendar()[:2], day.strftime('%d/%m/%Y'))} for day in weeks],
            'actual_basis_pending': True, 'undated_shipments': undated,
        }

    @api.model
    def _dashboard_row(self, key, name):
        return {'key': key, 'name': name, 'planned_kg': 0.0, 'planned_usd': 0.0,
                'actual_kg': 0.0, 'actual_usd': None, 'actual_price': None}
