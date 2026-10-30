"""Use the real supplier/T138 result, without duplicating its payroll policy."""
from math import isfinite

from odoo import models, _
from odoo.exceptions import UserError
from odoo.addons.step_payroll_contracts.history import history_protected
from odoo.addons.step_hr_contract_days.models.hr_payslip import HrPayslip as ContractDaysPayslip


class Payslip(models.Model):
    _inherit = 'hr.payslip'

    def _get_worked_day_lines_values(self, domain=None):
        normal = self._step_contract_days_access(sources=True)
        values = super(Payslip, normal)._get_worked_day_lines_values(domain=domain)
        types = normal.env['hr.work.entry.type'].browse([row['work_entry_type_id'] for row in values])
        types.check_access('read')
        types.check_field_access_rights('read', ['name', 'code'])
        for row in values:
            kind = types.browse(row['work_entry_type_id'])
            if not kind.exists() or not kind.code or not kind.name:
                raise UserError(_('Select the original typed day name and code before calculating T138.'))
            if row.get('code') and row['code'] != kind.code:
                raise UserError(_('The T138 worked-day code differs from its original type.'))
            if row.get('contract_id') and row['contract_id'] != normal.contract_id.id:
                raise UserError(_('The T138 worked day belongs to another contract.'))
            # The native provider supplies only its original type relation on
            # newly appended WORK100/late rows. OCA also requires these real
            # master descriptors and contract FK; no master is manufactured.
            row.setdefault('name', kind.name)
            row.setdefault('code', kind.code)
            row.setdefault('contract_id', normal.contract_id.id)
        return values

    def _step_compute_contract_days_sheet(self):
        # OCA's real work-entry adapter refreshes the complete typed rows before
        # running salary rules. Keep T138's admission/savepoint and its values
        # hook; the native-only pre-refresh must not reprice stale draft rows
        # before that actual OCA refresh has had the opportunity to run.
        return super(ContractDaysPayslip, self).compute_sheet()


class WorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    def _compute_payment(self):
        normal = self.sudo(False)
        rows = normal.filtered(lambda line: not history_protected(line.payslip_id))
        rows.check_access('read')
        rows.check_field_access_rights('read', ['payslip_id', 'work_entry_type_id',
            'number_of_days', 'number_of_hours', 'is_paid'])
        pending = []
        for slip in rows.payslip_id:
            slip = slip._step_contract_days_access(sources=True)
            if slip.struct_id.name != 'Nómina Chile':
                continue
            slip.check_field_access_rights('read', ['struct_id', 'contract_id', 'date_from', 'date_to'])
            slip.struct_id.check_field_access_rights('read', ['use_work_entries'])
            if not slip.struct_id.use_work_entries:
                raise UserError(_('Enable the original actual-work-entry policy before using T138 on Community.'))
            if not slip.contract_id.get_work_hours(slip.date_from, slip.date_to):
                raise UserError(_('Generate actual work entries before calculating T138 days on Community.'))
            # These values come from the real API -> AGPL -> T138 chain; this
            # bridge never chooses a divisor, derives missing days or reprices
            # an absent supplier amount from today's contract wage.
            values = slip._get_worked_day_lines_values()
            for line in rows.filtered(lambda day: day.payslip_id == slip):
                matches = [value for value in values if value['work_entry_type_id'] == line.work_entry_type_id.id]
                if len(matches) != 1:
                    raise UserError(_('The original T138 typed day is missing or ambiguous.'))
                value = matches[0]
                if 'amount' not in value:
                    # No supplier amount exists for this absence. Retain the
                    # original unpaid M2M policy; never infer it from a code.
                    continue
                if any(not isfinite(float(value.get(name, float('nan')))) for name in
                        ('number_of_days', 'number_of_hours', 'amount')):
                    raise UserError(_('The original T138 day values must be finite.'))
                if (abs(line.number_of_days - value['number_of_days']) > 0.000001
                        or abs(line.number_of_hours - value['number_of_hours']) > 0.000001):
                    raise UserError(_('Refresh the actual typed T138 days before calculating their payment.'))
                pending.append((line, value['amount']))
        # Authorize and validate the entire set before the first assignment.
        # The existing provider checks original unpaid policy and restores
        # closed SQL snapshots; frozen rows never reach the live helpers above.
        result = super(WorkedDays, normal)._compute_payment()
        for line, amount in pending:
            # Preserve supplier zeros on lateness/OUT instead of adding their
            # deduction back; never turn an originally unpaid type into pay.
            line.amount = amount if line.is_paid else 0.0
        return result
