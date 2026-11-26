"""Calendar-year YTD across contracts for the original Cerro structure."""
from odoo import models


class Payslip(models.Model):
    _inherit = 'hr.payslip'

    def _step_allows_cross_contract_ytd(self, previous_slips):
        self.ensure_one()
        original = self.env.ref('hr_payroll.structure_002', raise_if_not_found=False)
        if not original or self.struct_id != original or not self.contract_id:
            return super()._step_allows_cross_contract_ytd(previous_slips)
        contracts = previous_slips.contract_id | self.contract_id
        contracts.check_access('read')
        contracts.check_field_access_rights('read', ['employee_id', 'company_id'])
        return all(slip.contract_id for slip in previous_slips) and all(
            contract.employee_id == self.employee_id and contract.company_id == self.company_id
            for contract in contracts)
