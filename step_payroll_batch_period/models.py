from datetime import datetime, time, timedelta
import pytz
from odoo import fields, models, _

_PERIOD_SCOPE = object()


def period_bounds(contract, start, end):
    zone = pytz.timezone(contract.resource_calendar_id.tz or contract.employee_id.tz
                         or contract.company_id.resource_calendar_id.tz or 'UTC')
    first = zone.localize(datetime.combine(fields.Date.to_date(start), time.min)).astimezone(pytz.utc)
    last = zone.localize(datetime.combine(fields.Date.to_date(end) + timedelta(days=1), time.min)).astimezone(pytz.utc)
    return first.replace(tzinfo=None), last.replace(tzinfo=None)


class WorkEntry(models.Model):
    _inherit = 'hr.work.entry'

    def _step_entries_in_batch_period(self, start, end):
        bounds = {}
        def intersects(entry):
            contract = entry.contract_id
            if contract.id not in bounds:
                bounds[contract.id] = period_bounds(contract, start, end)
            first, last = bounds[contract.id]
            return entry.date_start < last and entry.date_stop > first
        return self.filtered(intersects)

    def _check_if_error(self):
        scope = self.env.context.get('_steps_batch_period')
        if scope and scope[0] is _PERIOD_SCOPE:
            # The native wizard fetches a one-day buffer for generation. That
            # buffer must not block October because September has conflicts.
            relevant = self._step_entries_in_batch_period(scope[1], scope[2])
            return super(WorkEntry, relevant.with_context(_steps_batch_period=None))._check_if_error()
        return super()._check_if_error()


class PayslipEmployees(models.TransientModel):
    _inherit = 'hr.payslip.employees'

    def compute_sheet(self):
        self.ensure_one()
        run = self.env['hr.payslip.run'].browse(self.env.context.get('active_id')).exists()
        start = run.date_start or self.env.context.get('default_date_start')
        end = run.date_end or self.env.context.get('default_date_end')
        if not start or not end:
            return super().compute_sheet()
        scoped = self.with_context(_steps_batch_period=(_PERIOD_SCOPE, start, end))
        result = super(PayslipEmployees, scoped).compute_sheet()
        if (isinstance(result, dict) and result.get('tag') == 'display_notification'):
            conflicts = self.env['hr.work.entry'].search([
                ('employee_id', 'in', self.employee_ids.ids), ('state', '=', 'conflict'),
                ('date_start', '<', fields.Date.to_date(end) + timedelta(days=2)),
                ('date_stop', '>', fields.Date.to_date(start) - timedelta(days=1)),
            ])._step_entries_in_batch_period(start, end)
            if conflicts:
                lines = []
                for entry in conflicts.sorted(key=lambda w: (w.employee_id.name or '', w.date_start, w.id)):
                    zone = pytz.timezone(entry.contract_id.resource_calendar_id.tz or 'UTC')
                    first = pytz.utc.localize(entry.date_start).astimezone(zone)
                    last = pytz.utc.localize(entry.date_stop).astimezone(zone)
                    lines.append('%s: %s → %s (%s; entrada %s)' % (
                        entry.employee_id.name, first.strftime('%d/%m/%Y %H:%M'),
                        last.strftime('%d/%m/%Y %H:%M'), zone.zone, entry.id))
                result = dict(result, params=dict(result.get('params', {}),
                    title=_('Conflictos de entradas de trabajo en el período de nómina'),
                    message=_('Revise las entradas indicadas antes de generar el lote:\n%s', '\n'.join(lines)),
                    sticky=True))
        return result
