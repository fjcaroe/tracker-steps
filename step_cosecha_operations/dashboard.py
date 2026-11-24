"""Read the operational harvest dashboard from its original company records."""
from datetime import datetime, time, timedelta, timezone
from math import isfinite
from zoneinfo import ZoneInfo

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HarvestCompany(models.Model):
    _inherit = 'res.company'

    harvest_hours_per_day = fields.Float(string='Horas por jornada de cosecha', default=8.0, required=True)

    @api.constrains('harvest_hours_per_day')
    def _check_harvest_hours_per_day(self):
        for company in self:
            if not isfinite(company.harvest_hours_per_day) or not 0 < company.harvest_hours_per_day <= 24:
                raise ValidationError(_('Las horas por jornada deben ser mayores que cero y no superar 24.'))


class HarvestSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    harvest_hours_per_day = fields.Float(related='company_id.harvest_hours_per_day', readonly=False)


class HarvestDashboard(models.Model):
    _inherit = 'step.cosecha.registry'

    @api.model
    def _dashboard_period(self, period):
        labels = {'today': 'Hoy', 'yesterday': 'Ayer', '7': 'Últimos 7 días',
            '30': 'Últimos 30 días', '90': 'Últimos 90 días', 'all': 'Todo el histórico'}
        if period not in labels:
            raise ValidationError(_('Seleccione un período válido.'))
        if period == 'all':
            return [], [], labels[period]
        today = fields.Date.context_today(self)
        last = today if period != 'yesterday' else today - timedelta(days=1)
        first = last - timedelta(days=int(period) - 1) if period.isdigit() else last
        end = last + timedelta(days=1)
        tz = ZoneInfo(self.env.context.get('tz') or self.env.user.tz or 'UTC')

        def utc(day):
            value = datetime.combine(day, time.min, tzinfo=tz).astimezone(timezone.utc)
            return fields.Datetime.to_string(value.replace(tzinfo=None))

        return [('date', '>=', utc(first)), ('date', '<', utc(end))], [
            ('date', '>=', fields.Date.to_string(first)), ('date', '<', fields.Date.to_string(end))], labels[period]

    @api.model
    def _dashboard_master(self, model, ident):
        master = self.env[model]
        scope = ['|', ('company_id', '=', False), ('company_id', '=', self.env.company.id)] if 'company_id' in master._fields else []
        if ident:
            try:
                ident = int(ident)
            except (TypeError, ValueError):
                raise ValidationError(_('Seleccione un maestro disponible en esta empresa.'))
            if ident <= 0 or not master.search_count(scope + [('id', '=', ident)]):
                raise ValidationError(_('Seleccione un maestro disponible en esta empresa.'))
        return master.search(scope, order='name, id'), ident or False

    def _dashboard_metrics(self):
        self.ensure_one()
        own = self.type_tarea == 'propio'
        lines = self.registry_line if own else self.registry_tarja_line
        workers = len(lines.mapped('employee_id'))
        hours = sum((line.hrs or 0.0) + ((line.hrs_extra or 0.0) if own else 0.0) for line in lines)
        cost = None
        if self.state in ('costo', 'cont'):
            # Native cost computes also assign ordinary stored rate/salary fields.
            # Evaluate them on virtual copies so opening this read-only dashboard
            # cannot rewrite the original workers, rates or historic harvest.
            cost_field = 'cost_empresa' if own else 'trato_total'
            cost = self.company_id.currency_id.round(sum(line.new(origin=line)[cost_field] for line in lines))
        kilos = self.total_kilos or 0.0
        return {'workers': workers, 'hours': hours,
            'average_kg': kilos / hours * self.company_id.harvest_hours_per_day if hours > 0 else None,
            'total_cost': cost, 'cost_per_kg': cost / kilos if cost is not None and kilos > 0 else None}

    @api.model
    def get_dashboard_data(self, days=None, period=None, species_id=False, farm_id=False, offset=0):
        period = str(period or ('all' if days == 0 else days if days is not None else 'today'))
        dates, reception_dates, label = self._dashboard_period(period)
        species, species_id = self._dashboard_master('step.especie', species_id)
        farms, farm_id = self._dashboard_master('step.fundo', farm_id)
        domain = [('company_id', '=', self.env.company.id)] + dates
        reception_domain = [('company_id', '=', self.env.company.id)] + reception_dates
        if farm_id:
            domain.append(('fundo_id', '=', farm_id))
            reception_domain.append(('registry_id.fundo_id', '=', farm_id))
        if species_id:
            for target, prefix in ((domain, ''), (reception_domain, 'registry_id.')):
                target.extend(['|', (prefix + 'especie_id', '=', species_id), '&',
                    (prefix + 'especie_id', '=', False),
                    (prefix + 'variedad_id.especie_id', '=', species_id)])
        count = self.search_count(domain)
        try:
            offset = max(0, int(offset))
        except (TypeError, ValueError):
            raise ValidationError(_('Página no válida.'))
        limit = 50
        if offset >= count:
            offset = max(0, ((count - 1) // limit) * limit)
        records = self.search(domain, order='date desc, id desc', limit=limit, offset=offset)
        totals = self.read_group(domain, ['total_kilos:sum', 'total_boxes:sum'], [])
        totals = totals[0] if totals else {}
        reception = self.env['step.cosecha.recepcion']
        reception_totals = reception.read_group(reception_domain, ['total_kilos:sum', 'observed_count:sum'], [])
        reception_totals = reception_totals[0] if reception_totals else {}
        states = {key: self.search_count(domain + [('state', '=', key)]) for key in ('in', 'apro', 'costo', 'cont')}
        types = {key: self.search_count(domain + [('type_tarea', '=', key)]) for key in ('propio', 'contratista')}
        history = self.env['step.history.cosecha']
        history_domain = [('company_id', '=', self.env.company.id)] if 'company_id' in history._fields else []
        rows = []
        state_labels = dict(self._fields['state'].selection)
        type_labels = dict(self._fields['type_tarea'].selection)
        for record in records:
            rows.append({'id': record.id, 'name': record.display_name,
                'date': fields.Datetime.to_string(record.date) if record.date else False,
                'date_label': fields.Datetime.context_timestamp(record, record.date).strftime('%d-%m-%Y') if record.date else 'Sin fecha',
                'type': record.type_tarea, 'type_label': type_labels.get(record.type_tarea, ''),
                'state': record.state, 'state_label': state_labels.get(record.state, ''),
                'fundo': record.fundo_id.display_name or '',
                'species': (record.especie_id or record.variedad_id.especie_id).display_name or '',
                'kilos': record.total_kilos or 0.0, **record._dashboard_metrics()})
        return {'company_name': self.env.company.display_name,
            'period': period, 'period_label': label, 'days': 0 if period == 'all' else int(period) if period.isdigit() else 1,
            'species': [{'id': row.id, 'name': row.display_name} for row in species],
            'farms': [{'id': row.id, 'name': row.display_name} for row in farms],
            'species_id': species_id, 'farm_id': farm_id,
            'hours_per_day': self.env.company.harvest_hours_per_day,
            'can_configure': self.env.user.has_group('base.group_system'),
            'currency_symbol': self.env.company.currency_id.symbol,
            'currency_name': self.env.company.currency_id.name,
            'currency_digits': self.env.company.currency_id.decimal_places,
            'kpis': {'records': count, 'kilos': totals.get('total_kilos', 0.0) or 0.0,
                'boxes': totals.get('total_boxes', 0.0) or 0.0,
                'received': self.search_count(domain + [('cos_recibida', '=', True)]),
                'pending_receipt': self.search_count(domain + [('type_tarea', '=', 'contratista'),
                    ('state', '=', 'cont'), ('cos_recibida', '=', False)]),
                'history': history.search_count(history_domain)},
            'states': states, 'types': types, 'recent': rows, 'offset': offset, 'limit': limit,
            'receptions': reception.search_count(reception_domain),
            'reception_in_progress': reception.search_count(reception_domain + [('state', 'in', ('draft', 'progress'))]),
            'reception_quality_alerts': reception_totals.get('observed_count', 0) or 0,
            'reception_kilos': reception_totals.get('total_kilos', 0.0) or 0.0,
            'locations': self.env['step.cosecha.ubicacion'].search_count([('company_id', '=', self.env.company.id)]),
            'processes': self.env['step.cosecha.proceso'].search_count([('company_id', '=', self.env.company.id)])}
