from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCompanyLayout(TransactionCase):
    def test_only_the_receipt_company_controls_the_format(self):
        company = self.env.company
        other = self.env['res.company'].create({'name': 'QA Nómina'})
        payslips = self.env['hr.payslip'].with_company(other)
        selected = payslips.new({'company_id': company.id})
        unselected = payslips.new({'company_id': other.id})
        settings = self.env['ir.config_parameter']
        key = 'step_payroll_steps_report.company_id'
        settings.set_param(key, False)
        self.assertFalse(selected._step_uses_steps_payroll_layout())
        settings.set_param(key, str(company.id))
        self.assertTrue(selected._step_uses_steps_payroll_layout())
        self.assertFalse(unselected._step_uses_steps_payroll_layout())
