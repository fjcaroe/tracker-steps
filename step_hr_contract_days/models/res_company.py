from math import ceil

from odoo import fields, models
from odoo.tools.float_utils import float_round


class ResCompany(models.Model):
    _inherit = "res.company"

    payroll_whole_days_meal = fields.Boolean(string="Colación por días enteros")
    payroll_whole_days_transport = fields.Boolean(string="Movilización por días enteros")


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def step_whole_day_allowance(self, monthly_amount):
        self.ensure_one()
        contract = self.contract_id
        start = max(self.date_from, contract.date_start)
        end = min(self.date_to, contract.date_end or self.date_to)
        paid_days = sum(
            line.number_of_days
            for line in self.worked_days_line_ids
            if line.work_entry_type_id.code in ("WORK100", "LEAVECL120")
        )
        # Avoid rounding binary float noise above an integer into an extra day.
        whole_days = ceil(float_round(paid_days, precision_digits=8))
        payable_days = max(0, min(whole_days, (end - start).days + 1, 30))
        return monthly_amount * payable_days / 30.0
