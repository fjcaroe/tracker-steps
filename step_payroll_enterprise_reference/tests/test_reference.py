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

    def test_repeated_input_amounts_aggregate_without_changing_rows(self):
        PayrollContractMixin.test_repeated_input_amounts_aggregate_without_changing_rows(self)

    def test_repeated_input_nonlinear_rule_is_evaluated_per_line(self):
        PayrollContractMixin.test_repeated_input_nonlinear_rule_is_evaluated_per_line(self)

    def test_quantities_rates_and_categories_preserve_clp_rounding(self):
        PayrollContractMixin.test_quantities_rates_and_categories_preserve_clp_rounding(self)

    def test_fractional_negative_rate_uses_real_engine(self):
        PayrollContractMixin.test_fractional_negative_rate_uses_real_engine(self)

    def test_actual_work_entries_types_and_domain(self):
        PayrollContractMixin.test_actual_work_entries_types_and_domain(self)

    def test_calendar_timezone_clips_work_entry_at_payroll_boundary(self):
        PayrollContractMixin.test_calendar_timezone_clips_work_entry_at_payroll_boundary(self)

    def test_chile_concept_rounding_matches_known_salary_cases(self):
        PayrollContractMixin.test_chile_concept_rounding_matches_known_salary_cases(self)

    def test_chile_final_quantity_rate_and_signed_halves(self):
        PayrollContractMixin.test_chile_final_quantity_rate_and_signed_halves(self)

    def test_out_of_contract_days_use_original_calendar(self):
        PayrollContractMixin.test_out_of_contract_days_use_original_calendar(self)

    def test_stored_essential_distinct_rule_identities_are_not_summed(self):
        PayrollContractMixin.test_stored_essential_distinct_rule_identities_are_not_summed(self)

    def test_stored_same_rule_rows_remain_additive_and_stable(self):
        PayrollContractMixin.test_stored_same_rule_rows_remain_additive_and_stable(self)

    def test_stored_nonessential_distinct_rules_keep_additive_contract(self):
        PayrollContractMixin.test_stored_nonessential_distinct_rules_keep_additive_contract(self)
