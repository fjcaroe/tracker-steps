"""Private real OCA records for printing; no original payroll is recalculated."""
from odoo import api, Command, fields


class StoredReportFixture:
    def setUp(self):
        super().setUp()
        self.company = self.env['res.company'].create({'name': 'Private stored PDF company',
            'country_id': self.env.ref('base.cl').id, 'currency_id': self.env.ref('base.CLP').id})
        self.actor = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Private stored PDF manager', 'login': 'private-stored-pdf-manager',
            'company_id': self.company.id, 'company_ids': [Command.set(self.company.ids)],
            'groups_id': [Command.set([self.env.ref(name).id for name in
                ('base.group_user', 'payroll.group_payroll_manager', 'hr.group_hr_manager')])]})
        self.scope = api.Environment(self.env.cr, self.actor.id, dict(self.env.context,
            allowed_company_ids=self.company.ids, no_reset_password=True, tracking_disable=True,
            mail_notrack=True, mail_create_nosubscribe=True, mail_notify_force_send=False), su=False)
        self.kind = self.scope['hr.payroll.structure.type'].create({'name': 'Private stored PDF type'})
        self.structure = self.scope['hr.payroll.structure'].create({'name': 'Private stored PDF structure',
            'code': 'PRIVATE_PRINT', 'company_id': self.company.id, 'type_id': self.kind.id,
            'use_worked_day_lines': False, 'payslip_name': '<literal> Stored remuneration', 'active': True})
        self.employee = self.scope['hr.employee'].create({'name': 'Private stored PDF employee', 'company_id': self.company.id})
        self.contract = self.scope['hr.contract'].create({'name': 'Private stored PDF contract',
            'employee_id': self.employee.id, 'company_id': self.company.id, 'date_start': fields.Date.today().replace(day=1),
            'wage': 1000, 'schedule_pay': 'monthly', 'structure_type_id': self.kind.id,
            'struct_id': self.structure.id, 'state': 'open'})
        self.categories = {code: self.scope['hr.salary.rule.category'].create({'name': 'Private stored ' + code, 'code': code})
                           for code in ('IMP', 'GROSS', 'NET', 'others', 'TOTAL_DESC', 'PRIVATE_UNKNOWN')}
        self.rules = {}
        for index, (code, category) in enumerate((('BASIC', 'IMP'), ('GROSS', 'GROSS'), ('NET', 'NET'),
                ('NEGATIVE', 'others'), ('ZERO', 'IMP'), ('NULL_VALUE', 'IMP'), ('OTHER', 'PRIVATE_UNKNOWN'),
                ('TOTAL_DED', 'TOTAL_DESC'))):
            self.rules[code] = self.scope['hr.salary.rule'].create({'name': 'Stored ' + code,
                'code': code, 'sequence': index + 1, 'struct_id': self.structure.id,
                'category_id': self.categories[category].id, 'condition_select': 'none',
                'amount_select': 'fix', 'amount_fix': 0, 'appears_on_payslip': True})

    def closed_slip(self, split_net=False, ambiguous_net=False):
        slip = self.scope['hr.payslip'].create({'name': 'Original stored payslip name', 'number': 'PRIVATE/PDF/1',
            'employee_id': self.employee.id, 'company_id': self.company.id, 'contract_id': self.contract.id,
            'struct_id': self.structure.id, 'date_from': fields.Date.today().replace(day=1),
            'date_to': fields.Date.end_of(fields.Date.today(), 'month')})
        values = {'BASIC': 100, 'GROSS': 100, 'NET': 75, 'NEGATIVE': -25, 'ZERO': 0,
                  'NULL_VALUE': 0, 'OTHER': 12, 'TOTAL_DED': 25}
        for code, amount in values.items():
            rule = self.rules[code]
            self.scope['hr.payslip.line'].create({'slip_id': slip.id, 'salary_rule_id': rule.id,
                'name': rule.name, 'code': rule.code, 'category_id': rule.category_id.id, 'sequence': rule.sequence,
                'amount': amount, 'quantity': 1, 'rate': 100, 'appears_on_payslip': True})
        if split_net or ambiguous_net:
            rule = self.rules['NET'].copy({'name': 'Stored other NET identity'}) if ambiguous_net else self.rules['NET']
            self.scope['hr.payslip.line'].create({'slip_id': slip.id, 'salary_rule_id': rule.id,
                'name': rule.name, 'code': rule.code, 'category_id': rule.category_id.id, 'amount': 25,
                'quantity': 1, 'rate': 100, 'appears_on_payslip': True})
        work_type = self.scope['hr.work.entry.type'].create({'name': 'Private stored work', 'code': 'PRIVATE_PDF_WORK'})
        self.scope['hr.payslip.worked_days'].create({'name': 'Stored attendance', 'code': 'PRIVATE_PDF_WORK',
            'payslip_id': slip.id, 'contract_id': self.contract.id, 'work_entry_type_id': work_type.id,
            'number_of_days': 2, 'number_of_hours': 16})
        slip.write({'state': 'done', 'paid': True})
        self.env.flush_all()
        null_line = slip.line_ids.filtered(lambda line: line.code == 'NULL_VALUE')
        # A private imported-history fixture only; the report must not coerce or
        # repair this physical NULL when printing it as an absent amount.
        self.env.cr.execute('UPDATE hr_payslip_line SET total=NULL WHERE id=%s', [null_line.id])
        return slip

    def stored_snapshot(self, slip):
        result = []
        for table, inverse in (('hr_payslip', 'id'), ('hr_payslip_line', 'slip_id'),
                               ('hr_payslip_worked_days', 'payslip_id')):
            self.env.cr.execute('SELECT to_jsonb(t) FROM ' + table + ' t WHERE ' + inverse + '=%s ORDER BY id', [slip.id])
            result.append(self.env.cr.fetchall())
        return result

    def employee_actor(self, login='private-stored-pdf-employee'):
        group = self.env.ref('l10n_cl_simpledigital_payroll.group_hr_payroll_employee', raise_if_not_found=False)
        if not group:
            self.skipTest('The Simple Digital employee role is required for this permission case')
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Private stored PDF owner', 'login': login, 'company_id': self.company.id,
            'company_ids': [Command.set(self.company.ids)],
            'groups_id': [Command.set((self.env.ref('base.group_user') | group).ids)]})
        return user

    def rendered_html(self, slip, user=None):
        reports = self.scope['ir.actions.report']
        if user:
            reports = reports.with_user(user)
        return reports._render_qweb_html('payroll.action_report_payslip', slip.ids)[0]
