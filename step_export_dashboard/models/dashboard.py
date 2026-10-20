"""Read-only T96 comparisons over existing sales programmes and shipments."""
from datetime import date, timedelta
from odoo import api, models, _
from odoo.exceptions import ValidationError
from odoo.osv import expression


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
            ('company_id', 'in', companies)])
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
        actual_usd = {}
        moves = self.env['account.move']
        can_read_amounts = moves.check_access_rights('read', raise_exception=False)
        if can_read_amounts and shipments:
            links = [[('step_export_shipment_id', 'in', shipments.ids)],
                     [('reversed_entry_id.step_export_shipment_id', 'in', shipments.ids)]]
            if 'debit_origin_id' in moves._fields:
                links.append([('debit_origin_id.step_export_shipment_id', 'in', shipments.ids)])
            domain = expression.AND([[('company_id', 'in', companies), ('state', '=', 'posted'),
                                      ('move_type', 'in', ['out_invoice', 'out_refund'])], expression.OR(links)])
            usd = self.env.ref('base.USD')
            for move in moves.search(domain):
                shipment = move.step_export_shipment_id or move.reversed_entry_id.step_export_shipment_id
                if not shipment and 'debit_origin_id' in moves._fields:
                    shipment = move.debit_origin_id.step_export_shipment_id
                sign = -1 if move.move_type == 'out_refund' else 1
                amount = move.currency_id._convert(move.amount_untaxed, usd, move.company_id,
                                                  move.invoice_date or move.date, round=False)
                actual_usd[shipment.id] = actual_usd.get(shipment.id, 0.0) + sign * amount
        undated = 0
        for shipment in shipments:
            shipped = shipment.state in ('shipped', 'invoiced', 'settled')
            if not shipped and shipment.id not in actual_usd:
                continue
            if not shipment.date:
                undated += 1
            if selected(shipment.date, shipment.season_id):
                for row in rows(shipment.sales_program_id, shipment.species_id, shipment.company_id):
                    row['actual_kg'] += shipment.kg_qty if shipped else 0.0
                    if can_read_amounts:
                        row['actual_usd'] = (row['actual_usd'] or 0.0) + actual_usd.get(shipment.id, 0.0)

        def finish(items):
            values = sorted(items.values(), key=lambda item: item['name'])
            total = self._dashboard_row('total', _('Totales'))
            for row in values:
                for key in ('planned_kg', 'planned_usd', 'actual_kg'):
                    total[key] += row[key]
            if can_read_amounts:
                total['actual_usd'] = sum(row['actual_usd'] or 0.0 for row in values)
            for row in values + [total]:
                if can_read_amounts:
                    row['actual_usd'] = row['actual_usd'] or 0.0
                    row['actual_price'] = row['actual_usd'] / row['actual_kg'] if row['actual_kg'] else None
                row['planned_price'] = row['planned_usd'] / row['planned_kg'] if row['planned_kg'] else None
            return {'rows': values, 'total': total}

        return {
            'species': finish(species_rows), 'programs': finish(program_rows),
            'seasons': [{'id': season.id, 'name': season.display_name} for season in seasons],
            'months': months,
            'weeks': [{'id': day.isoformat(), 'name': '%s-W%02d · %s' % (*day.isocalendar()[:2], day.strftime('%d/%m/%Y'))} for day in weeks],
            'amounts_restricted': not can_read_amounts, 'undated_shipments': undated,
        }

    @api.model
    def _dashboard_row(self, key, name):
        return {'key': key, 'name': name, 'planned_kg': 0.0, 'planned_usd': 0.0,
                'actual_kg': 0.0, 'actual_usd': None, 'actual_price': None}
