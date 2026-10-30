"""Exact anchored first-init history chain; no database or runtime execution.

The normal engine profile stays separate. This consumes the existing anchored
NUMERIC/company/properties/HR-storage profile before its UI manifest changes.
"""
import json
import os
from pathlib import Path, PurePosixPath

import build_numeric_input_engine as numeric
import derive_original_anchor_company as company
import derive_original_anchor_properties as properties
import derive_original_payroll_storage as storage
import derive_original_history_deletion as deletion
import original_history_engine_contract as contract


REPORT = "oca-original-anchor-history-deletion.json"


def _guard_files(source):
    if isinstance(source, dict):
        return source
    root = Path(source).resolve()
    return {name: (root / (PurePosixPath(name).relative_to("step_payroll_oca_api")
        if root.name == "step_payroll_oca_api" else PurePosixPath(name))).read_bytes()
        for name in contract.GUARD_PATHS}


def verify_anchor_inputs(actual, accounting_actual, expected, accounting_expected):
    contract.need(contract.inventory(actual) == contract.inventory(expected),
        "exact-numeric-company-properties-hr-storage-input-required")
    contract.need(numeric.hashes(accounting_actual) == numeric.hashes(accounting_expected),
        "exact-existing-anchored-accounting-properties-required")


def plan_anchor_history_deletion(original, accounting, schema_raw, capsule_raw, guard_source):
    """Rebuild all anchored intermediates, never infer the input from a receipt."""
    contract.inventory(original)
    contract.need(isinstance(schema_raw, bytes) and contract.sha(schema_raw) == storage.SCHEMA_PLAN_SHA256,
        "sealed-original-storage-plan-required")
    contract.need(isinstance(capsule_raw, bytes) and contract.sha(capsule_raw) == company.CAPSULE_SHA256,
        "sealed-original120-capsule-required")
    # This gate precedes every call to the CASCADE field derivation. The
    # receipt proves source/import presence, never runtime guard execution.
    guard = contract.guard_contract(_guard_files(guard_source))
    schema, capsule = json.loads(schema_raw), json.loads(capsule_raw)
    numeric_files = numeric.plan(original)
    global_files, company_audit = company.plan(numeric_files, capsule)
    modules, property_contract = properties.plan({"payroll": global_files, "payroll_account": accounting}, capsule)
    property_files = modules["payroll"]
    input_files, storage_contract = storage.plan_storage(property_files, schema, anchor_properties=True)
    final, deletion_proof = deletion.plan_history_deletion(input_files)
    stages = []
    for name, before, after, changed in (
            ("numeric-input", original, numeric_files, [numeric.FILE]),
            ("original-global-company", numeric_files, global_files, [company.FILE]),
            ("original-properties", global_files, property_files,
                sorted(name for module, name in properties.EDITS if module == "payroll")),
            ("original-hr-storage", property_files, input_files, sorted(storage.EDITS)),
            ("original-company-run-deletion", input_files, final, [deletion.FILE])):
        first, last = contract.inventory(before), contract.inventory(after)
        contract.need(sorted(path for path in first if first[path] != last[path]) == sorted(changed),
            "unexpected-anchored-stage-file-change:" + name)
        stages.append({"stage": name, "before_files": first, "after_files": last,
            "changed_files": sorted(changed), "complete_file_count": 144})
    contract.need(contract.protected_ast(original) == contract.protected_ast(final),
        "anchored-payroll-methods-defaults-imports-or-identities-changed")
    contract.need(original["__manifest__.py"] == final["__manifest__.py"], "anchored-vendor-manifest-changed")
    report = {"schema": 1, "profile": "anchored-original-history-storage-composition",
        "oca_pin": numeric.PIN, "license": "LGPL-3", "source_file_count": 144,
        "schema_plan_sha256": contract.sha(schema_raw), "capsule_sha256": contract.sha(capsule_raw),
        "original_source_files": contract.inventory(original), "input_files": contract.inventory(input_files),
        "candidate_files": contract.inventory(final), "changed_files_from_existing_anchor": [deletion.FILE],
        "stages": stages, "actual_api_guard": guard,
        "accounting_source_files": numeric.hashes(accounting),
        "accounting_property_files": numeric.hashes(modules["payroll_account"]),
        "company_initializer_audit": company_audit, "original_property_contract": property_contract,
        "original_storage_contract": storage_contract,
        "deletion_derivation": dict(deletion_proof,
            builder_sha256=contract.sha(contract.lf(Path(deletion.__file__).read_bytes()))),
        "builder_sources_lf_sha256": {Path(module.__file__).name: contract.sha(contract.lf(Path(module.__file__).read_bytes()))
            for module in (numeric, company, properties, storage, deletion, contract)},
        "builder_lf_sha256": contract.sha(contract.lf(Path(__file__).read_bytes())),
        "anchored_properties_profile": True, "normal_engine_profile": False,
        "existing_values_converted": False, "defaults_changed": False, "payroll_runtime_methods_changed": False,
        "database_accessed": False, "source_checkout_changed": False, "artifact_python_executed": False,
        "requires_pre_orm_company_null_admission": True, "runtime_guard_execution_certified": False,
        "historical_rows_rewritten": False, "paid_payroll_recalculated": False,
        "operational_acceptance": False, "integral_conversion": False, "deadline_resolved": False}
    return input_files, final, modules["payroll_account"], report


def apply_anchor_history_deletion(oca, engine, schema_plan, capsule, guard_source):
    """After HR's three declarations and BEFORE any UI/manifest derivation."""
    oca, engine = Path(oca).resolve(), Path(engine).resolve()
    contract.need(engine.is_relative_to(Path("/opt/steps-validation")) and engine != oca,
        "private-anchored-history-engine-required")
    schema_raw, capsule_raw = Path(schema_plan).read_bytes(), Path(capsule).read_bytes()
    original, accounting = numeric.source_files(oca), properties.accounting_source_files(oca)
    before, candidate, account_candidate, report = plan_anchor_history_deletion(
        original, accounting, schema_raw, capsule_raw, guard_source)
    output = engine / "payroll"
    verify_anchor_inputs(contract._snapshot(output), contract._snapshot(engine / "payroll_account"), before, account_candidate)
    receipt = engine.parent / REPORT
    contract.need(not receipt.exists(), "new-anchored-history-receipt-required")
    # Every gate completed before this single admitted private file write.
    (output / deletion.FILE).write_bytes(candidate[deletion.FILE])
    contract.need(contract.inventory(contract._snapshot(output)) == contract.inventory(candidate),
        "anchored-final-history-engine-bytes-differ")
    with os.fdopen(os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return report
