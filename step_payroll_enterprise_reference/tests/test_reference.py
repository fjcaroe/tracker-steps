from odoo.tests import TransactionCase, tagged
from odoo.addons.step_payroll_contracts.testing import PayrollContractMixin


@tagged('post_install','-at_install')
class EnterpriseReferenceCase(PayrollContractMixin,TransactionCase):
    payroll_group='hr_payroll.group_hr_payroll_manager'

    def test_real_engine_typed_input_and_liquid_code(self):
        PayrollContractMixin.test_real_engine_typed_input_and_liquid_code(self)

    def test_line_values_missing_codes_and_multi_slip_sum(self):
        PayrollContractMixin.test_line_values_missing_codes_and_multi_slip_sum(self)

    def test_line_values_reads_do_not_change_validated_lines(self):
        PayrollContractMixin.test_line_values_reads_do_not_change_validated_lines(self)

    def test_rules_receive_real_record_and_mapping_get(self):
        PayrollContractMixin.test_rules_receive_real_record_and_mapping_get(self)

    def test_actual_accounting_entry_balances(self):
        PayrollContractMixin.test_actual_accounting_entry_balances(self)

    def test_portal_cannot_read_salary_lines(self):
        PayrollContractMixin.test_portal_cannot_read_salary_lines(self)
