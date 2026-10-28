"""Work-entry payroll boundary using actual Community contracts and calendars."""
from collections import defaultdict
from datetime import datetime, time, timedelta

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.tools.float_utils import float_round


class WorkEntryType(models.Model):
    _inherit = 'hr.work.entry.type'

    round_days = fields.Selection([('NO', 'No rounding'), ('HALF', 'Half day'),
                                   ('FULL', 'Full day')], default='NO', required=True)
    round_days_type = fields.Selection([('HALF-UP', 'Closest'), ('UP', 'Up'), ('DOWN', 'Down')],
                                       default='DOWN', required=True)


class Contract(models.Model):
    _inherit = 'hr.contract'

    def _payroll_period_bounds(self, date_from, date_to):
        self.ensure_one()
        calendar = self.resource_calendar_id or self.employee_id.resource_calendar_id
        zone = pytz.timezone(calendar.tz or 'UTC')
        bounds = (datetime.combine(fields.Date.to_date(date_from), time.min),
                  datetime.combine(fields.Date.to_date(date_to), time.max))
        return tuple(zone.localize(value).astimezone(pytz.UTC).replace(tzinfo=None) for value in bounds)

    def get_work_hours(self, date_from, date_to, domain=None):
        """Read actual entries within calendar-local dates, without elevating access."""
        self.check_access('read')
        totals = defaultdict(float)
        first, last = fields.Date.to_date(date_from), fields.Date.to_date(date_to)
        if not first or not last or first > last:
            raise UserError(_('A valid payroll period is required.'))
        for contract in self:
            calendar = contract.resource_calendar_id or contract.employee_id.resource_calendar_id
            if not calendar:
                raise UserError(_('Work-entry payroll requires a working calendar.'))
            start, stop = contract._payroll_period_bounds(first, last)
            entries = self.env['hr.work.entry'].search(expression.AND([domain or [], [
                ('contract_id', '=', contract.id), ('company_id', '=', contract.company_id.id),
                ('state', 'in', ['draft', 'validated']), ('date_start', '<', stop), ('date_stop', '>', start)]]))
            for entry in entries:
                if not entry.work_entry_type_id:
                    raise UserError(_('Every payroll work entry must retain its type.'))
                left, right = max(start, entry.date_start), min(stop, entry.date_stop)
                if entry.date_start >= start and entry.date_stop <= stop:
                    hours = entry.duration
                elif entry.work_entry_type_id.is_leave:
                    hours = contract.employee_id._get_work_days_data_batch(
                        pytz.UTC.localize(left), pytz.UTC.localize(right), compute_leaves=False,
                        calendar=calendar)[contract.employee_id.id]['hours']
                else:
                    hours = (right-left).total_seconds()/3600
                totals[entry.work_entry_type_id.id] += hours
        return dict(totals)


class Structure(models.Model):
    _inherit = 'hr.payroll.structure'

    out_of_contract_work_entry_type_id = fields.Many2one('hr.work.entry.type', ondelete='restrict',
        string='Tipo para fuera de contrato')

    use_work_entries = fields.Boolean(string='Usar entradas de trabajo', default=False,
        help='Explicit opt-in. Read actual work entries; keep legacy OCA calendar payroll otherwise.')


class WorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    work_entry_type_id = fields.Many2one('hr.work.entry.type', ondelete='restrict')


class Payslip(models.Model):
    _inherit = 'hr.payslip'

    def _get_worked_day_lines_hours_per_day(self):
        self.ensure_one()
        return self.contract_id.resource_calendar_id.hours_per_day

    def _round_days(self, work_entry_type, days):
        if work_entry_type.round_days == 'NO':
            return days
        return float_round(days, precision_rounding=0.5 if work_entry_type.round_days == 'HALF' else 1,
                           rounding_method=work_entry_type.round_days_type)

    def _get_worked_day_lines_values(self, domain=None):
        self.ensure_one()
        self.check_access('read')
        self.contract_id.ensure_one()
        hours_per_day = self._get_worked_day_lines_hours_per_day()
        if not hours_per_day or hours_per_day <= 0:
            raise UserError(_('Payroll requires positive calendar hours per day.'))
        hours = self.contract_id.get_work_hours(self.date_from, self.date_to, domain=domain)
        # Keep the total days residue on the largest attendance group.
        result, residue = [], 0.0
        ordered = sorted(hours, key=lambda kind: (hours[kind], kind))
        for index, kind in enumerate(ordered):
            entry_type = self.env['hr.work.entry.type'].browse(kind)
            days = round(hours[kind]/hours_per_day, 5)
            adjusted = days + residue if index == len(ordered)-1 else days
            rounded = self._round_days(entry_type, adjusted)
            residue += adjusted-rounded if index == len(ordered)-1 else days-rounded
            result.append({'sequence': entry_type.sequence, 'work_entry_type_id': kind,
                'number_of_days': rounded, 'number_of_hours': hours[kind],
                'name': entry_type.name, 'code': entry_type.code, 'contract_id': self.contract_id.id})
        return sorted(result, key=lambda row: (row['sequence'], row['work_entry_type_id']))

    def _get_out_of_contract_calendar(self):
        self.ensure_one()
        contract = self.contract_id
        if 'time_credit' in contract._fields and contract.time_credit and 'standard_calendar_id' in contract._fields:
            return contract.standard_calendar_id
        return contract.resource_calendar_id

    def _get_worked_day_lines(self, domain=None, check_out_of_contract=True):
        self.ensure_one()
        rows = self._get_worked_day_lines_values(domain=domain)
        if not check_out_of_contract:
            return rows
        contract = self.contract_id
        calendar = self._get_out_of_contract_calendar()
        if not calendar:
            raise UserError(_('Out-of-contract payroll requires its original calendar.'))
        ranges = []
        if contract.date_start and self.date_from < contract.date_start:
            ranges.append((self.date_from,min(self.date_to,contract.date_start-timedelta(days=1))))
        if contract.date_end and contract.date_end < self.date_to:
            ranges.append((max(self.date_from,contract.date_end+timedelta(days=1)),self.date_to))
        zone = pytz.timezone(calendar.tz or 'UTC')
        days = hours = 0.0
        for first, last in ranges:
            if first > last:
                continue
            start = zone.localize(datetime.combine(first,time.min))
            stop = zone.localize(datetime.combine(last,time.max))
            duration = calendar.get_work_duration_data(start,stop,compute_leaves=False)
            days += duration['days'];hours += duration['hours']
        if days or hours:
            kind = self.struct_id.out_of_contract_work_entry_type_id
            if not kind:
                # Reuse the preserved supplier master if its original XML ID exists.
                kind = self.env.ref('hr_payroll.hr_work_entry_type_out_of_contract',raise_if_not_found=False)
            if not kind:
                raise UserError(_('Select the original out-of-contract work-entry type on the salary structure.'))
            rows.append({'sequence':kind.sequence,'work_entry_type_id':kind.id,
                'name':kind.name,'code':kind.code,'contract_id':contract.id,
                'number_of_days':days,'number_of_hours':hours})
        return rows

    def get_worked_day_lines(self, contracts, date_from, date_to):
        if not self.struct_id.use_work_entries:
            return super().get_worked_day_lines(contracts, date_from, date_to)
        self.ensure_one()
        if contracts != self.contract_id or date_from != self.date_from or date_to != self.date_to:
            raise UserError(_('Work-entry payroll requires the payslip own contract and period.'))
        return self._get_worked_day_lines()

    def compute_sheet(self):
        if any(slip.paid or slip.state not in ('draft','verify') for slip in self):
            raise UserError(_('Validated or paid payroll cannot be recalculated.'))
        pending = []
        for slip in self.filtered(lambda record: record.struct_id.use_work_entries):
            actual = slip._get_worked_day_lines_values()
            if not actual:
                raise UserError(_('Generate actual work entries before calculating this payroll.'))
            rows = slip._get_worked_day_lines()
            start, stop = slip.contract_id._payroll_period_bounds(slip.date_from,slip.date_to)
            if self.env['hr.work.entry'].search_count([
                    ('contract_id','=',slip.contract_id.id),('company_id','=',slip.company_id.id),
                    ('state','=','conflict'),('date_start','<',stop),('date_stop','>',start)]):
                raise UserError(_('Resolve conflicting work entries before calculating payroll.'))
            existing = {}
            for line in slip.worked_days_line_ids:
                if not line.work_entry_type_id or line.work_entry_type_id.id in existing or line.contract_id != slip.contract_id:
                    raise UserError(_('Adopt the original worked-day type relations before enabling work-entry payroll.'))
                existing[line.work_entry_type_id.id] = line
            pending.append((slip, rows, existing))
        # Validate the whole batch first. A later engine error rolls back the refresh too.
        with self.env.cr.savepoint():
            for slip, rows, existing in pending:
                current = {row['work_entry_type_id'] for row in rows}
                for row in rows:
                    kind = row['work_entry_type_id']
                    if kind in existing:
                        existing[kind].write(row)
                    else:
                        self.env['hr.payslip.worked_days'].create(dict(row,payslip_id=slip.id))
                for kind, line in existing.items():
                    if kind not in current:
                        line.write({'number_of_days':0.0,'number_of_hours':0.0})
            return super().compute_sheet()
