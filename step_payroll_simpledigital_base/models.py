from odoo import models


LEGACY_GROSS = "result = categories['BASIC'] + categories['ALW']"
COMPANY_PARAMETER = 'step_payroll_simpledigital_base.company_id'


class SalaryRule(models.Model):
    _inherit = 'hr.salary.rule'

    def _compute_rule(self, localdict):
        self.ensure_one()
        if (self.code == 'GROSS' and self.amount_select == 'code'
                and (self.amount_python_compute or '').strip() == LEGACY_GROSS
                and self.struct_id == self.env.ref(
                    'l10n_cl_simpledigital_payroll.structure_chile', raise_if_not_found=False)):
            slip = localdict.get('payslip')
            company_id = self.env['ir.config_parameter'].sudo().get_param(COMPANY_PARAMETER)
            if slip and company_id == str(slip.company_id.id):
                return localdict['categories'].get('IMP', 0.0), 1.0, 100.0
        return super()._compute_rule(localdict)
