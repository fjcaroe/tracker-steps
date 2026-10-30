"""Real private master data shared by native and Community contract-day cases."""
from datetime import date, datetime, time, timedelta

from odoo import api, Command


class ContractDaysFixture:
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'Private T138 fixture',
            'country_id': cls.env.ref('base.cl').id, 'currency_id': cls.env.ref('base.CLP').id})
        group = cls.env.ref('payroll.group_payroll_manager', raise_if_not_found=False)
        if not group:
            group = cls.env.ref('hr_payroll.group_hr_payroll_manager')
        groups = [cls.env.ref(alias).id for alias in ('base.group_user', 'hr.group_hr_manager',
            'hr_holidays.group_hr_holidays_manager', 'account.group_account_manager')] + group.ids
        user = cls.env['res.users'].with_context(no_reset_password=True).create({'name': 'Private T138 manager',
            'login': 'private-t138-manager', 'company_id': cls.company.id,
            'company_ids': [Command.set(cls.company.ids)], 'groups_id': [Command.set(groups)], 'tz': 'UTC'})
        cls.scope = api.Environment(cls.env.cr, user.id,
            dict(cls.env.context, allowed_company_ids=cls.company.ids, lang='en_US'), su=False)
        cls.work = cls.scope.ref('hr_work_entry.work_entry_type_attendance')
        assert cls.work.code == 'WORK100'
        attendance = {'name': 'Private shift', 'hour_from': 8, 'hour_to': 16}
        if 'work_entry_type_id' in cls.scope['resource.calendar.attendance']._fields:
            attendance['work_entry_type_id'] = cls.work.id
        cls.calendar = cls.scope['resource.calendar'].create({'name': 'Private T138 calendar', 'tz': 'UTC',
            'company_id': cls.company.id, 'attendance_ids': [Command.clear()] + [Command.create(dict(attendance,
                dayofweek=str(day))) for day in range(5)]})
        cls.kind = cls.scope['hr.payroll.structure.type'].create({'name': 'Private T138 type'})
        if 'default_work_entry_type_id' in cls.kind._fields:
            cls.kind.default_work_entry_type_id = cls.work
        cls.journal = cls.scope['account.journal'].create({'name': 'Private T138 salary', 'code': 'P138',
            'company_id': cls.company.id, 'type': 'general'})
        cls.debit = cls.scope['account.account'].create({'name': 'Private T138 expense', 'code': '938001',
            'account_type': 'expense', 'company_ids': [Command.set(cls.company.ids)]})
        cls.credit = cls.scope['account.account'].create({'name': 'Private T138 liability', 'code': '938002',
            'account_type': 'liability_current', 'company_ids': [Command.set(cls.company.ids)]})
        cls.category = cls.scope['hr.salary.rule.category'].create({'name': 'Private T138 category', 'code': 'PRIVATE_T138'})
        cls.generic = cls._structure('Private T138 generic')
        values = {'name': 'Private real T138 rule', 'code': 'PRIVATE_T138_RESULT', 'struct_id': cls.generic.id,
            'category_id': cls.category.id, 'sequence': 1, 'condition_select': 'none', 'amount_select': 'code',
            'amount_python_compute': 'result = 1.0', 'account_debit': cls.debit.id, 'account_credit': cls.credit.id}
        if 'company_id' in cls.scope['hr.salary.rule']._fields:
            values['company_id'] = cls.company.id
        cls.rule = cls.scope['hr.salary.rule'].create(values)
        cls.env['ir.sequence'].create({'name': 'Private T138 numbering', 'code': 'salary.slip',
            'company_id': cls.company.id, 'implementation': 'no_gap', 'prefix': 'PRIVATE/T138/'})

    @classmethod
    def _structure(cls, name):
        values = {'name': name, 'code': 'PRIVATE_T138_%s' % name.replace(' ', '_'), 'type_id': cls.kind.id}
        for field, value in (('company_id', cls.company.id), ('parent_id', False),
                ('country_id', cls.company.country_id.id), ('use_work_entries', True),
                ('use_worked_day_lines', True), ('journal_id', cls.journal.id)):
            if field in cls.scope['hr.payroll.structure']._fields:
                values[field] = value
        return cls.scope['hr.payroll.structure'].create(values)

    def _slip(self, structure=None, year=2026, month=10, last=31, entry=1, exit=None, wage=600000):
        structure = structure if structure is not None else self.generic
        author = self.env['hr.contract'].with_company(self.company).env
        employee = author['hr.employee'].create({'name': 'Private T138 employee', 'company_id': self.company.id})
        values = {'name': 'Private T138 contract', 'employee_id': employee.id, 'company_id': self.company.id,
            'state': 'open', 'date_start': date(year, month, entry),
            'date_end': date(year, month, exit) if exit else False, 'wage': wage,
            'structure_type_id': self.kind.id, 'resource_calendar_id': self.calendar.id}
        for field, value in (('struct_id', structure.id), ('journal_id', self.journal.id),
                ('schedule_pay', 'monthly'), ('wage_type', 'monthly')):
            if field in author['hr.contract']._fields:
                values[field] = value
        if 'contract_type_id' in author['hr.contract']._fields:
            field = author['hr.contract']._fields['contract_type_id']
            values['contract_type_id'] = author[field.comodel_name].search([], limit=1).id
        field = author['hr.contract']._fields.get('analytic_account_id')
        if field and field.required:
            plan = author['account.analytic.plan'].create({'name': 'Private T138 analytic plan'})
            values['analytic_account_id'] = author['account.analytic.account'].create({'name': 'Private T138 analytic',
                'plan_id': plan.id, 'company_id': self.company.id}).id
        contract = author['hr.contract'].create(values)
        contract.resource_calendar_id = self.calendar
        employee.resource_calendar_id = self.calendar
        employee.resource_id.tz = 'UTC'
        contract = contract.with_env(self.scope)
        first = date(year, month, entry)
        while first.weekday() > 4:
            first += timedelta(days=1)
        self._entry(contract, self.work, datetime.combine(first, time(8)), 8)
        slip = self.scope['hr.payslip'].create({'name': 'Private T138 payslip',
            'number': 'PRIVATE/T138/FIXTURE/%s' % contract.id, 'employee_id': employee.id,
            'company_id': self.company.id, 'contract_id': contract.id, 'struct_id': structure.id,
            'date_from': date(year, month, 1), 'date_to': date(year, month, last)})
        return slip

    def _entry(self, contract, kind, start, hours):
        return self.scope['hr.work.entry'].create({'name': 'Private T138 actual entry', 'employee_id': contract.employee_id.id,
            'contract_id': contract.id, 'company_id': self.company.id, 'work_entry_type_id': kind.id,
            'date_start': start, 'date_stop': start + timedelta(hours=hours)})

    def _type(self, code):
        values = {'name': 'Private T138 ' + code, 'code': code, 'is_leave': True}
        if 'country_id' in self.scope['hr.work.entry.type']._fields:
            values['country_id'] = self.company.country_id.id
        return self.scope['hr.work.entry.type'].create(values)

    def _leave(self, slip, kind, first, last, unpaid=False):
        # Explicit private payroll policy, distinct from the leave master's
        # own unpaid marker. Neither relationship is inferred by the product.
        if 'unpaid_structure_ids' in kind._fields:
            kind.unpaid_structure_ids = [Command.link(slip.struct_id.id)]
        values = {'name': 'Private T138 real leave type', 'unpaid': unpaid,
            'work_entry_type_id': kind.id, 'requires_allocation': 'no', 'leave_validation_type': 'no_validation'}
        if 'company_id' in self.scope['hr.leave.type']._fields:
            values['company_id'] = self.company.id
        master = self.scope['hr.leave.type'].create(values)
        leave = self.scope['hr.leave'].create({'name': 'Private T138 real leave', 'employee_id': slip.employee_id.id,
            'holiday_status_id': master.id, 'request_date_from': first, 'request_date_to': last})
        if leave.state != 'validate':
            leave.action_validate()
        # Exercise the real typed source, including on runtimes that have not
        # yet generated the new leave's work entry for this private contract.
        existing = self.scope['hr.work.entry'].search([('contract_id', '=', slip.contract_id.id),
            ('work_entry_type_id', '=', kind.id), ('date_start', '<=', leave.date_to), ('date_stop', '>=', leave.date_from)])
        if not existing:
            self._entry(slip.contract_id, kind, leave.date_from, (leave.date_to - leave.date_from).total_seconds() / 3600)
        return leave

    def _snapshot(self, slips):
        self.env.flush_all()
        result = {}
        for table, column, ids in (('hr_payslip', 'id', slips.ids), ('hr_payslip_worked_days', 'payslip_id', slips.ids),
                ('hr_payslip_input', 'payslip_id', slips.ids), ('hr_payslip_line', 'slip_id', slips.ids),
                ('hr_contract', 'id', slips.contract_id.ids), ('hr_work_entry', 'contract_id', slips.contract_id.ids),
                ('hr_leave', 'employee_id', slips.employee_id.ids)):
            self.env.cr.execute('SELECT to_jsonb(t) FROM ' + table + ' t WHERE ' + column + '=ANY(%s) ORDER BY id', (ids,))
            result[table] = self.env.cr.fetchall()
        move_ids = slips.move_id.ids
        for table, column in (('account_move', 'id'), ('account_move_line', 'move_id')):
            self.env.cr.execute('SELECT to_jsonb(t) FROM ' + table + ' t WHERE ' + column + '=ANY(%s) ORDER BY id', (move_ids,))
            result[table] = self.env.cr.fetchall()
        return result
