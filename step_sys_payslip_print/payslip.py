from odoo import models
from odoo.exceptions import AccessError


class Payslip(models.Model):
    _inherit = "hr.payslip"

    def _sys_print_contract_wage(self):
        self.ensure_one()
        slip = self.sudo(False)
        slip.check_access("read")
        slip.check_field_access_rights("read", ["contract_id"])
        contract = slip.contract_id
        if not contract:
            return None
        try:
            contract.check_access("read")
            contract.check_field_access_rights("read", ["company_id", "wage"])
        except AccessError:
            return None
        if contract.company_id != slip.company_id:
            return None
        return contract.wage
