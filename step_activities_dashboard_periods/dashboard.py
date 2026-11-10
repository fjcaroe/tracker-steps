from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression


_SCOPE = object()
_CONTEXT_KEY = '_step_activities_dashboard_period'


def period_domain(env, domain):
    scope = env.context.get(_CONTEXT_KEY)
    if isinstance(scope, tuple) and scope and scope[0] is _SCOPE:
        return expression.AND([domain, list(scope[1])])
    return domain


class CrewDashboard(models.Model):
    _inherit = 'hr.salary.custom'

    def _search(self, domain, *args, **kwargs):
        return super()._search(period_domain(self.env, domain), *args, **kwargs)

    @api.model
    def get_activities_period_dashboard(self, period='day'):
        if period not in ('day', 'week', 'month', 'season'):
            raise UserError(_('Seleccione un período del panel de Actividades.'))

        company = self.env.company
        today = fields.Date.context_today(self)
        domain = [('company_id', '=', company.id), ('date', '<=', today)]
        crews = self.search(domain, order='date desc, id desc', limit=1)
        tasks = self.env['step.tarja'].search(domain, order='date desc, id desc', limit=1)
        dates = [date for date in (crews.date, tasks.date) if date]
        anchor = max(dates, default=today)
        start = end = anchor
        label = _('Último día')
        if period == 'week':
            start = anchor - timedelta(days=anchor.weekday())
            end = start + timedelta(days=6)
            label = _('Semana')
        elif period == 'month':
            start, end = fields.Date.start_of(anchor, 'month'), fields.Date.end_of(anchor, 'month')
            label = _('Mes')
        elif period == 'season':
            season = self.env['step.temporada'].search([
                ('company_id', '=', company.id), ('start_date', '<=', anchor), ('end_date', '>=', anchor),
            ], order='start_date desc, id desc', limit=1)
            start, end = season.start_date, season.end_date
            label = season.display_name if season else _('Sin temporada para la fecha')

        dates_domain = [('date', '>=', start), ('date', '<=', end)] if start and end else [('id', '=', False)]
        scoped = self.with_context(**{_CONTEXT_KEY: (_SCOPE, tuple(dates_domain))})
        result = scoped.get_activities_dashboard_data(0)
        contractor_lines = scoped.env['step.tarja.cost.line']
        totals = contractor_lines._read_group(
            [('tarja_cost_id.company_id', '=', company.id), ('tarja_cost_id.tarja_type', '=', 'contratista'),
             *[('tarja_cost_id.' + field, operator, value) for field, operator, value in dates_domain]],
            [], ['trato_total:sum'],
        )
        contractor_cost = (totals[0][0] or 0) if totals else 0
        result['kpis'].update(contractor_cost=contractor_cost,
                              total_cost=result['kpis']['company_cost'] + contractor_cost)
        result['period_label'] = (
            f'{label} · {start:%d/%m/%Y}' + (f' – {end:%d/%m/%Y}' if start != end else '') if start else label
        )
        result['period'] = period
        return result


class Task(models.Model):
    _inherit = 'step.tarja'

    def _search(self, domain, *args, **kwargs):
        return super()._search(period_domain(self.env, domain), *args, **kwargs)
