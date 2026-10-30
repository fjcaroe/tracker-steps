"""The same storage witnesses on the actual unchanged native provider."""
from odoo.tests import TransactionCase, tagged
from odoo.addons.step_payroll_contracts.history_storage_testing import HistoryStorageCases


@tagged('post_install', '-at_install')
class NativeHistoryStorageCase(HistoryStorageCases, TransactionCase):
    payroll_group = 'hr_payroll.group_hr_payroll_manager'
    oca = False

    def test_line_literal_remains_scalar_on_read(self):
        self.case_line_literal_does_not_inherit_master_translation_or_change_on_read()

    def test_rule_jsonb_translation_keeps_line_literal(self):
        self.case_rule_translation_uses_jsonb_without_translating_existing_line()

    def test_worked_day_null_remains_null_on_read(self):
        self.case_worked_day_null_is_created_and_read_without_backfill()

    def test_contract_calendar_null_and_real_set_null_fk(self):
        self.case_contract_calendar_is_nullable_and_actual_fk_sets_null()

    def test_portal_cannot_read_warm_line_name(self):
        self.case_history_storage_still_rejects_portal_actor_with_warm_cache()
