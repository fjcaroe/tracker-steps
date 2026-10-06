from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install','-at_install')
class TestTransition(TransactionCase):
    def test_rpc_context_cannot_clear_review(self):
        # A readonly widget does not protect write() over RPC. A caller cannot
        # forge the server's non-serializable confirmation token in JSON.
        contract=self.env['hr.contract'].browse()
        with self.assertRaises(UserError):
            contract.with_context(_confirm_payroll_migration=True).write({'step_payroll_migration_review':False})

    def test_legacy_structure_cannot_be_recomputed(self):
        structure=self.env['hr.payroll.structure'].new({'name':'Histórico QA','step_legacy_payroll':True})
        slip=self.env['hr.payslip'].new({'struct_id':structure})
        with self.assertRaises(UserError): slip.compute_sheet()
