import base64
import csv
import io

from odoo import _, api, Command, fields, models
from odoo.exceptions import UserError, ValidationError


class Payslip(models.Model):
    _inherit = 'hr.payslip'

    payment_report = fields.Binary(readonly=True, attachment=True)
    payment_report_date = fields.Date(readonly=True)
    payment_report_filename = fields.Char(readonly=True)

    def action_payslip_payment_report(self):
        self.ensure_one()
        self.check_access('write')
        return self.env['hr.payroll.payment.report.wizard']._generate_for(
            self.payslip_run_id, self)

    def _step_sys_payment_state(self, previous, target):
        self.check_access('write')
        self.check_field_access_rights('read', ['company_id', 'state', 'payslip_run_id'])
        if any(s.company_id != self.env.company or s.state != previous for s in self):
            raise UserError(_('Select payslips in the current company and expected payment state.'))
        if target == 'done' and any(s.payslip_run_id.state == 'paid' for s in self):
            raise UserError(_('Reopen payment on the paid batch before changing an individual payslip.'))
        self.write({'state': target})

    def action_payslip_paid(self):
        self._step_sys_payment_state('done', 'paid')

    def action_payslip_unpaid(self):
        self._step_sys_payment_state('paid', 'done')

    def action_register_payment(self):
        self.ensure_one()
        self.check_access('write')
        self.check_field_access_rights('read', ['company_id', 'state', 'move_id'])
        if self.company_id != self.env.company or self.state != 'done' or not self.move_id:
            raise UserError(_('Select a validated payslip with an accounting entry in the current company.'))
        self.move_id.check_access('read')
        if self.move_id.company_id != self.company_id or self.move_id.state != 'posted':
            raise UserError(_('Post the payroll accounting entry before registering a payment.'))
        return self.move_id.action_register_payment()


class PayrollPaymentReport(models.TransientModel):
    _name = 'hr.payroll.payment.report.wizard'
    _description = 'Payroll Payment Report'

    payslip_run_id = fields.Many2one('hr.payslip.run', ondelete='set null')
    payslip_ids = fields.Many2many(
        'hr.payslip', 'hr_payroll_payment_report_wizard_hr_payslip_rel',
        'hr_payroll_payment_report_wizard_id', 'hr_payslip_id', required=True)
    company_id = fields.Many2one('res.company', compute='_compute_company_id')
    export_format = fields.Selection([('csv', 'CSV')], required=True, default='csv')

    @api.model
    def _generate_for(self, batch, slips):
        with self.env.cr.savepoint():
            wizard = self.create({'payslip_run_id': batch.id, 'payslip_ids': [Command.set(slips.ids)],
                                  'export_format': 'csv'})
            return wizard.generate_payment_report()

    @api.depends('payslip_run_id.company_id', 'payslip_ids.company_id')
    def _compute_company_id(self):
        for wizard in self:
            wizard.company_id = wizard.payslip_run_id.company_id or wizard.payslip_ids[:1].company_id

    def _perform_checks(self):
        self.ensure_one()
        self.check_access('read')
        batch = self.payslip_run_id
        if batch:
            batch.check_access('write')
            batch.check_field_access_rights('read', ['company_id', 'state'])
            if batch.company_id != self.env.company or batch.state != 'close':
                raise UserError(_('Select a closed payroll batch in the current company.'))
        slips = self.payslip_ids
        slips.check_access('write')
        slips.check_field_access_rights('read', ['employee_id', 'company_id', 'payslip_run_id', 'state',
                                                'net_wage', 'date_from', 'date_to'])
        if (not batch and len(slips) != 1 or
                any(s.payslip_run_id != batch or s.company_id != self.env.company for s in slips)):
            raise UserError(_('Select payslips from the same batch and current company.'))
        eligible = slips.filtered(lambda s: s.state == 'done' and s.net_wage > 0)
        if not eligible:
            raise ValidationError(_('Select a validated payslip with a positive net wage.'))
        people = slips.mapped('employee_id')
        people.check_access('read')
        people.check_field_access_rights('read', ['name', 'bank_account_id', 'private_city', 'private_country_id',
                                                 'private_street2', 'private_street', 'private_zip'])
        banks = people.mapped('bank_account_id')
        banks.check_access('read')
        banks.check_field_access_rights('read', ['allow_out_payment', 'acc_number'])
        recipients = eligible.mapped('employee_id')
        missing = recipients.filtered(lambda employee: not employee.bank_account_id)
        if missing:
            raise UserError(_('Bank account missing for: %s', ', '.join(missing.mapped('name'))))
        untrusted = recipients.filtered(lambda employee: not employee.bank_account_id.allow_out_payment)
        if untrusted:
            raise UserError(_('Bank account awaiting verification for: %s', ', '.join(untrusted.mapped('name'))))

    def _payment_csv(self, report_date, slips):
        self.ensure_one()
        output = io.StringIO(newline='')
        writer = csv.writer(output)
        writer.writerow([_('Report Date'), _('Payslip Period'), _('Employee name'), _('Employee address'),
                         _('Bank account'), _('Amount to pay')])
        date_format = '%d/%m/%Y'
        for slip in slips:
            employee = slip.employee_id
            address = ' '.join(part or '' for part in (
                employee.private_street, employee.private_street2, employee.private_zip,
                employee.private_city, employee.private_country_id.name))
            period = '%s - %s' % (slip.date_from.strftime(date_format), slip.date_to.strftime(date_format))
            amount = '%s%s' % (slip.net_wage, slip.company_id.currency_id.symbol)
            writer.writerow([report_date.strftime(date_format), period, employee.name, address,
                             employee.bank_account_id.acc_number, amount])
        return output.getvalue().encode('utf-8')

    def generate_payment_report(self):
        self.ensure_one()
        with self.env.cr.savepoint():
            self._perform_checks()
            date = fields.Date.today()
            batch = self.payslip_run_id
            slips = self.payslip_ids
            values = {'payment_report': base64.b64encode(self._payment_csv(date, slips)),
                      'payment_report_date': date, 'payment_report_filename': (batch.name or slips.name) + '.csv'}
            if batch:
                batch.write(values)
            for slip in slips:
                individual = base64.b64encode(self._payment_csv(date, slip)) if len(slips) > 1 else values['payment_report']
                slip.write(dict(values, payment_report=individual))


class PayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    def action_payment_report(self):
        self.ensure_one()
        with self.env.cr.savepoint():
            members = self._step_sys_batch_members()
            return self.env['hr.payroll.payment.report.wizard']._generate_for(self, members)
