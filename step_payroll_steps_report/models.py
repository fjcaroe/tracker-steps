from odoo import models


class Payslip(models.Model):
    _inherit = 'hr.payslip'

    def _step_uses_steps_payroll_layout(self):
        self.ensure_one()
        company_id = self.env['ir.config_parameter'].sudo().get_param('step_payroll_steps_report.company_id')
        return company_id == str(self.company_id.id)
