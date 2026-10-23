"""Round each payable concept before the native engine accumulates categories."""
from datetime import date

from odoo import models
from odoo.tools.float_utils import float_round


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _step_clp_rounding_applies(self):
        self.ensure_one()
        chile_type = self.env.ref(
            'l10n_cl_simpledigital_payroll.structure_type_chile', raise_if_not_found=False)
        return bool(chile_type and self.struct_id.type_id == chile_type
                    and self.company_id.currency_id.name == 'CLP'
                    and self.date_from and self.date_from >= date(2026, 10, 1)
                    and self.state in ('draft', 'verify'))

    def _get_payslip_line_total(self, amount, quantity, rate, rule):
        total = super()._get_payslip_line_total(amount, quantity, rate, rule)
        if self._step_clp_rounding_applies():
            return float_round(total, precision_digits=0, rounding_method='HALF-UP')
        return total
