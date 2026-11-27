"""Run the two financial stages of the single corrected L-derived SyS fiscal and document rehearsal."""

import argparse
import fcntl
import gzip
import json
import os
from pathlib import Path
from types import SimpleNamespace

from build_sys_employee_view_profile import build_hr_profile
from build_sys_upgrade_policy_profile import fingerprint
from guard_sys_original_catalogue import checkpoint, ROOT, SEALED, SOURCE, TARGET
from rehearse_sys_module_upgrades import (
    DOCUMENT_MODULES, FINANCE_ARCHIVE, FORWARD, MODULES, PRIVATE, SPACE, candidate_batch, check_financial_actions,
    check_space, compare_operator_exports, digest, differences, final_receipt, forms, guards, module_versions, package_profile,
    payroll_exports, pin_original_providers, prepare_profile, print_chilean_invoices, query, require,
    restore_combined_filestore, retained_release, save, snapshot,
)
from restore_sys_previred_pair import LOCK


AUX = PRIVATE / "community-sys-documents-preserved-20261127U44FG"
SOURCE_SQL = "0c4e970e29579c6de38d71397a987682e97ff9a90027baad8c9e9b77f84bf606"
SOURCE_TREE = "71c9add47cf4265ee31555f42c02c8a819b8683154e53858490b22c6c11f8d1c"
DOCUMENT_TREE = "a9622742f0e70f7de2552e1f4f1b110444191d89661ed22378890798a4319825"
FIXTURES = {"res_company_users_rel": 2, "res_groups_users_rel": 6, "res_partner": 2, "res_users": 2}


def write_snapshot(file, data):
    with file.open("xb") as target:
        target.write(gzip.compress(json.dumps(data, sort_keys=True).encode(), mtime=0))


def accept_seed(args, proof):
    stage = AUX / "pre-fiscal-seed.json"
    require(digest(stage) == "a3e1dd3e3d928865ffa95790898d373c8b98ca773280e7be3c7dcd208fce53d4", "unreviewed-FG-source")
    seed = json.loads(stage.read_bytes())
    require(seed["all_original_rows_retained"] and seed["all_original_column_properties_and_constraints"] and
            seed["source_sql_sha256"] == proof["sql_sha256"] == SOURCE_SQL and seed["target"] == TARGET and
            seed["source"] == proof["source"] == SOURCE and seed["physical_tree_sha256"] == SOURCE_TREE and
            seed["added_fixture_rows"] == FIXTURES, "wrong-FG-seed")
    require(query("postgres", "SELECT s.spcname||'|'||pg_get_userbyid(d.datdba) FROM pg_database d "
                  f"JOIN pg_tablespace s ON s.oid=d.dattablespace WHERE d.datname='{TARGET}'") == SPACE + "|odoo",
            "unexpected-FG-owner-or-tablespace")
    original_guards = guards(SOURCE)
    require(len(original_guards) == 40 and guards(TARGET) == original_guards, "physical-FG-guard-drift")
    require(module_versions(TARGET) == module_versions(SOURCE), "untracked-FG-module-change")
    checkpoint(TARGET, "initial_seed", "before")
    baseline = snapshot(TARGET)
    original = json.loads(gzip.decompress((SEALED / "source-snapshot.json.gz").read_bytes()))
    delta = differences(original, baseline)
    require(set(delta["public_tables"]) == set(FIXTURES) and set(delta["sequence_values"]) == {"res_partner_id_seq", "res_users_id_seq"}
            and not any(v for k, v in delta.items() if k not in ("public_tables", "sequence_values")), "FG-fixture-delta")
    (ROOT / "runtime").mkdir(mode=0o755, exist_ok=True)
    (ROOT / "runtime").chmod(0o755)
    write_snapshot(ROOT / "finance-baseline.json.gz", baseline)
    save(ROOT / "restored.json", {"database": TARGET, "sealed": str(SEALED), "dump": SOURCE_SQL,
                                 "runtime": proof["runtime"]["archive_sha256"], "free": check_space(0), "rows": proof["rows"],
                                 "objects": 2679, "tablespace": SPACE, "guards": original_guards, "fixture_receipt": digest(stage)})


def finance(args, proof):
    if not (ROOT / "restored.json").exists():
        accept_seed(args, proof)
    if not (ROOT / "combined-source-files.json").is_file():
        restore_combined_filestore(args)
    if not (ROOT / "pinned-providers.json").is_file():
        pin_original_providers(args)
    if not (ROOT / "employee-profile.json").is_file():
        save(ROOT / "employee-profile.json", build_hr_profile(SEALED, ROOT))
    if not (ROOT / "profile-proof.json").is_file():
        prepare_profile(args)
    if not (ROOT / "upgrade-profile.json").is_file():
        package_profile(args, proof)
    require(digest(ROOT / "upgrade-profile.tar") == FINANCE_ARCHIVE, "previously-certified-financial-package-required")
    if not (ROOT / "final.json").is_file():
        candidate_batch(args, proof)
    if not (ROOT / "financial-storage.json").is_file():
        final_receipt(args, proof, "financial-storage.json")
    result = json.loads((ROOT / "financial-storage.json").read_bytes())
    require(all(result["official_results"].values()) and not result["covered_table_changes"] and
            not result["relaxed_original_required_columns"] and
            not any(result["full_sql_delta"][k] for k in ("columns", "constraints", "relation_owner_and_acl", "sequence_definitions")),
            "FG-financial-preservation-failed")
    if not (ROOT / "financial-delete-actions.json").is_file():
        check_financial_actions(args)
    before = json.loads((ROOT / "forms-before.json").read_bytes())
    after = json.loads((ROOT / "forms-after.json").read_bytes())
    require(before["directory"] == after["directory"], "public-directory-operator-scope-drift")
    checkpoint(TARGET, "final_finance", "after")
    doc = AUX / "documents/addons"
    require(set(p.name for p in doc.iterdir()) == set(DOCUMENT_MODULES) and fingerprint(doc) == (20, DOCUMENT_TREE),
            "original-document-source-unavailable")
    (ROOT / "document-addons").mkdir(mode=0o755, exist_ok=True)
    (ROOT / "document-addons").chmod(0o755)
    if not (ROOT / "document-provider-proof.json").is_file():
        save(ROOT / "document-provider-proof.json", {"files": 20, "sha256": DOCUMENT_TREE})


def final(args, proof, receipt, sha):
    require(receipt and receipt.resolve() == receipt and receipt.parent == AUX and receipt.is_file() and digest(receipt) == sha,
            "reviewed-protected-document-admission-required")
    states = module_versions(TARGET)
    require(len(states) == 192 and all(states[m] == ["installed", v] for m, v in DOCUMENT_MODULES.items()) and
            all(states[m] == ["installed", MODULES[m][1]] for m in FORWARD), "unaccepted-combined-versions")
    checkpoint(TARGET, "operator_workflows", "before")
    baseline = ROOT / "document-workflow-baseline.json.gz"
    if not baseline.is_file():
        write_snapshot(baseline, snapshot(TARGET))
        save(ROOT / "document-admission.json", {"proof": receipt.name, "sha256": sha})
    require(json.loads((ROOT / "document-admission.json").read_bytes())["sha256"] == sha, "different-document-acceptance")
    if not (ROOT / "combined-forms.json").is_file():
        args.label = "combined-forms"
        forms(args)
    operators = json.loads((ROOT / "combined-forms.json").read_bytes())
    finance_only = json.loads((ROOT / "forms-after.json").read_bytes())
    require(operators == finance_only, "combined-directory-or-business-action-scope-changed")
    if not (ROOT / "retained-release.json").is_file():
        retained_release(args)
    if not (ROOT / "release-exports.json").is_file():
        payroll_exports(args, "release-exports")
    if not (ROOT / "release-export-comparison.json").is_file():
        compare_operator_exports(args, "release-exports", "release-export-comparison")
    comparison = json.loads((ROOT / "release-export-comparison.json").read_bytes())
    require(comparison["originals_preserved"] and comparison["matches"], "combined-operator-exports-differ")
    print_chilean_invoices(args, proof)
    checkpoint(TARGET, "operator_workflows", "after")
    if not (ROOT / "combined-workflows-storage.json").is_file():
        result = final_receipt(args, proof, "combined-workflows-storage.json")
        require(not result["covered_table_changes"] and not result["relaxed_original_required_columns"] and
                not any(result["full_sql_delta"][k] for k in ("columns", "constraints", "relation_owner_and_acl", "sequence_definitions")),
                "post-workflow-original-storage-drift")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("finance", "final"))
    parser.add_argument("--document-admission", type=Path)
    parser.add_argument("--document-admission-sha256")
    cli = parser.parse_args()
    args = SimpleNamespace(database=TARGET, output=ROOT, sealed=SEALED)
    os.umask(0o077)
    with open(LOCK, "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        proof = json.loads((SEALED / "backup.json").read_bytes())
        if cli.stage == "finance":
            finance(args, proof)
        else:
            final(args, proof, cli.document_admission, cli.document_admission_sha256)
