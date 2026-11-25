"""Required original draft payslip fields, scoped to the private Cerro overlay."""
from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.addons.step_payroll_contracts.history import assert_mutable


class Payslip(models.Model):
    _inherit = 'hr.payslip'

    name = fields.Char(required=True)

    def write(self, values):
        if 'name' in values:
            assert_mutable(self.filtered(lambda slip: slip.name != values['name']))
        return super().write(values)

    def get_payslip_vals(self, date_from, date_to, employee_id=False, contract_id=False, struct_id=False):
        draft = self
        if not self and employee_id and date_from and date_to:
            employee = self.env['hr.employee'].browse(employee_id)
            if self.env.context.get('contract'):
                contract = (self.env['hr.contract'].browse(contract_id) if contract_id
                            else employee._get_contracts(date_from=date_from, date_to=date_to)[:1])
            else:
                contract = employee.contract_id
            structure = struct_id[0] if struct_id else contract.struct_id.id
            if contract and structure:
                draft = self.new({'employee_id': employee.id, 'company_id': employee.company_id.id,
                    'date_from': date_from, 'date_to': date_to, 'contract_id': contract.id,
                    'struct_id': structure})
        result = super(Payslip, draft).get_payslip_vals(date_from, date_to, employee_id, contract_id, struct_id)
        values = result['value']
        if values.get('contract_id') and values.get('struct_id') and not values.get('name'):
            naming = self.new({'employee_id': employee_id, 'date_from': date_from, 'date_to': date_to})
            naming._compute_name()
            values['name'] = naming.name
        return result

    def get_inputs(self, contracts, date_from, date_to):
        rows = super().get_inputs(contracts, date_from, date_to)
        if not rows:
            return rows
        kinds = self.struct_id.input_line_type_ids
        kinds.check_access('read')
        for row in rows:
            kind = kinds.filtered(lambda record: record.active and record.code == row['code'])
            if len(kind) != 1:
                raise UserError(_('Link each generated rule input to one original input type on its structure.'))
            row['input_type_id'] = kind.id
        return rows

    def _compute_worked_days(self, contract, day_from, day_to):
        row = super()._compute_worked_days(contract, day_from, day_to)
        kind = self.env.ref('hr_work_entry.work_entry_type_attendance')
        kind.check_access('read')
        if kind.code != row['code']:
            raise UserError(_('The generated attendance must use its original work-entry type.'))
        return dict(row, work_entry_type_id=kind.id)

    def _compute_leave_days(self, contract, day_from, day_to):
        rows = list(super()._compute_leave_days(contract, day_from, day_to))
        if not rows:
            return rows
        intervals = contract.employee_id.list_leaves(day_from, day_to, calendar=contract.resource_calendar_id)
        kinds = self.env['hr.work.entry.type']
        for _, _, interval in intervals:
            kinds |= interval[:1].holiday_id.holiday_status_id.work_entry_type_id
        kinds.check_access('read')
        for row in rows:
            kind = kinds.filtered(lambda record: record.code == row['code'])
            if len(kind) != 1:
                raise UserError(_('The generated leave must use an unambiguous original work-entry type.'))
            row['work_entry_type_id'] = kind.id
        return rows


class Input(models.Model):
    _inherit = 'hr.payslip.input'

    input_type_id = fields.Many2one(required=True)


class WorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    work_entry_type_id = fields.Many2one(required=True)
