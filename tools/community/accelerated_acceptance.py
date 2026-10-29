"""Exact HR consumer package used by the combined private acceptance runner.

This module only describes the package and creates private filesystem overlays.
Database creation, source backups, leases, upgrades and acceptance stay with the
main validator. Native reference remains a reference, never an OCA conversion.
"""
import ast
from pathlib import Path

from hr_consumers_candidate import MODULES as HR_MODULES, build


# These owned modules must be upgraded when already installed in the native
# clone. Passing only -i would leave old code/data versions silently untested.
NATIVE_HR_UPGRADE_MODULES = HR_MODULES
HR_TEST_METHODS = {
    ("step_hr_contract_lifecycle", "TestLegalWorkweekCalendar"): (
        "test_effective_hours_by_date", "test_official_row_protected", "test_official_row_unlink_protected",
        "test_custom_row_editable_without_technical_group", "test_upcoming_transition", "test_cron_idempotent_alert",
    ),
    ("step_hr_contract_lifecycle", "TestContractAdequacyBatch"): (
        "test_approve_requires_distribution_note",
    ),
    ("step_hr_contract_lifecycle", "TestSeveranceCalc"): (
        "test_feriado_proporcional_dt_example", "test_feriado_proporcional_no_service",
        "test_ias_anual_under_one_year_does_not_apply", "test_ias_anual_rounds_fraction_over_six_months",
        "test_ias_anual_tope_11_years", "test_ias_anual_tope_uf90", "test_ias_mensual_temporada",
        "test_ias_mensual_under_one_month", "test_mes_aviso",
    ),
    ("step_hr_contract_lifecycle", "TestContractWeeklyHours"): (
        "test_fractional_work_week_uses_real_global_attendance_without_lunch",
        "test_two_week_cycle_uses_actual_average_and_native_reference",
        "test_dated_and_resource_specific_schedule_require_contractual_review",
        "test_flexible_schedule_keeps_native_value_or_requires_original_reference",
        "test_two_week_schedule_cannot_hide_an_unassigned_original_week",
    ),
    ("step_payroll_engine_transition", "TestTransition"): (
        "test_rpc_context_cannot_clear_review", "test_legacy_structure_cannot_be_recomputed",
    ),
    ("step_payroll_engine_transition", "PayrollReviewCase"): (
        "test_batch_identifies_every_pending_contract_and_keeps_review_gate",
        "test_same_contract_is_not_repeated_for_multiple_slips",
        "test_missing_parameter_is_named_instead_of_generic_failure",
        "test_direct_flag_write_remains_protected", "test_non_manager_cannot_confirm",
        "test_legacy_payslip_cannot_be_recalculated",
    ),
    ("step_payroll_batch_period", "BatchPeriodCase"): (
        "test_september_conflicts_do_not_block_october_or_get_changed",
        "test_real_october_conflicts_remain_blocked",
        "test_local_midnight_and_intersecting_overnight_entries",
        "test_external_context_cannot_disable_normal_validation",
        "test_notification_identifies_all_workers_in_local_time",
        "test_dst_boundaries_use_real_short_and_long_santiago_days",
        "test_hidden_entry_and_contract_block_complete_batch_under_normal_actor",
        "test_closed_run_wrong_model_missing_run_and_invalid_dates_are_rejected",
        "test_wrong_company_context_is_rejected_without_new_payroll",
        "test_oca_real_wizard_creates_actual_days_and_preserves_original_entries",
        "test_oca_missing_actual_policy_or_entries_never_persist_theoretical_days",
        "test_oca_actual_engine_error_rolls_back_created_slips_and_private_number",
    ),
    ("steps_hr_payroll_correction", "HrConsumersCase"): (
        "test_closed_history_blocks_contract_work_entries_and_amounts",
        "test_open_paid_flag_is_not_recomputed", "test_open_history_lock_is_not_recomputed",
        "test_apply_rechecks_a_preview_validated_in_another_session",
        "test_rpc_requires_correction_group", "test_correction_cannot_cross_allowed_companies",
        "test_open_correction_uses_actual_engine_and_preserves_input_identity",
        "test_engine_failure_rolls_back_contract_and_work_entry_changes",
        "test_calendar_termination_cutoff_uses_local_day", "test_crossing_work_entry_requires_real_hour_review",
        "test_existing_relation_tables_and_acl_ownership_remain", "test_community_refuses_theoretical_days_before_mutation",
        "test_lifecycle_has_real_city_payslip_relations_views_and_menus",
        "test_lifecycle_preserves_paid_severance_and_worker_identity",
        "test_transition_uses_actual_payroll_manager_and_keeps_review_on_missing_masters",
        "test_transition_preserves_structure_and_forbids_old_engine_recalculation",
        "test_weekly_hours_feed_all_contract_consumers_without_changing_the_schedule",
        "test_hidden_work_entries_cannot_be_deleted_through_the_correction_role",
    ),
}
HR_TEST_COUNT = sum(len(methods) for methods in HR_TEST_METHODS.values())
HR_TEST_TAGS = ",".join("/" + module + ":" + cls for module, cls in HR_TEST_METHODS)


def verify_hr_test_inventory(source):
    """Fail if the declared class/method count drifts before creating databases."""
    found = {}
    for module in HR_MODULES:
        for path in (Path(source) / module / "tests").glob("test_*.py"):
            for cls in ast.parse(path.read_text(encoding="utf-8-sig")).body:
                if isinstance(cls, ast.ClassDef):
                    methods = tuple(node.name for node in cls.body if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"))
                    if methods:
                        found[(module, cls.name)] = methods
    if found != HR_TEST_METHODS:
        raise ValueError("HR consumer test inventory drift; review the exact method list")
    return HR_TEST_COUNT


def prepare_hr_overlay(source, stage, overlay, *, community):
    """Return the extra CE-only addons root, or add native source links normally."""
    source, stage, overlay = Path(source), Path(stage), Path(overlay)
    verify_hr_test_inventory(source)
    if community:
        target = stage / "consumer-addons"
        build(source, target, community=True)
        return target
    for module in HR_MODULES:
        target = overlay / module
        if target.exists():
            if target.resolve() != (source / module).resolve():
                raise ValueError("Conflicting native consumer source: " + module)
        else:
            target.symlink_to(source / module)
    return None


def hr_native_flags(installed_names):
    """Choose -i versus -u from the clone's registry, not from its source checkout."""
    installed = set(installed_names)
    create = [name for name in HR_MODULES if name not in installed]
    upgrade = [name for name in NATIVE_HR_UPGRADE_MODULES if name in installed]
    return (["-i", ",".join(create)] if create else []) + (["-u", ",".join(upgrade)] if upgrade else [])
