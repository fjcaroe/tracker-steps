"""Capture and cold-boot the tested fiscal, payroll and document product on its private, read-only database."""
from collections import Counter
import fcntl
import json
import os
from pathlib import Path
import pwd
import shutil
import sys
from types import SimpleNamespace

from admit_sys_combined_documents import PACKAGE, restore_files
from admit_sys_preserved_document_product import CHECKS, decode, qualified_odoo, run_fiscal_shell
from capture_sys_combined_source import DOCUMENT_SHA, ORIGIN, PAYROLL_SHA, capacity, physical_bundle
from complete_converted_filestore import inventory
from custody_sys_previred_filestore import attachments, digest, object_catalog
from prepare_sys_fiscal_document_seed import AUX, FG, FG_RUNTIME, SOURCE_ARCHIVE
from restore_converted_sys_cohort import check_modules, full_snapshot, open_as_user, package, save, verify_same
from restore_native_product_backup import query
from restore_sys_previred_pair import LOCK, require

OUT = AUX / "final-custody"
INTENDED_RECOVERY = "COMMUNITY_SYS_PREVIRED_RECOVERY_20261127U44FG"
ORIGINALS = {
    "original-documents-release.tar": (PACKAGE, DOCUMENT_SHA),
    "original-fiscal-release.tar": (FG_RUNTIME / "upgrade-profile.tar", "ca9180cdd5d3be9b5e69073d83171760cef34b22b07ae0a7cb38940cbd63ce37"),
    "original-policy-release.tar": (CHECKS / "original-public-addons.tar", "e1ab99abe55ac7693afe6c48f3ee51aa4ac27208b483472a6e8ae20f0be6233b"),
    "original-employee-release.tar": (FG_RUNTIME / "employee-profile.tar", "91c782849b652422c4324a9c8cf7dc9cf50323b1569515127e95a8dc20af7feb"),
}


def active_sources(modules, launcher, fiscal_profile):
    core = SOURCE_ARCHIVE / "runtime"
    mounts = [(FG_RUNTIME / "document-addons", AUX / "documents/addons"),
              *((FG_RUNTIME / name, FG_RUNTIME / name) for name in ("employee-profile", "pinned")), (fiscal_profile, fiscal_profile)]
    original = {}
    inside = {}
    for name in modules:
        variants = [(observed / name, actual / name) for observed, actual in mounts if (actual / name).is_dir()]
        require(len(variants) <= 1, "overlapping-qualified-providers")
        if not variants:
            rel = Path("odoo/addons/base") if name == "base" else Path("addons") / name
            variants = [(FG_RUNTIME / "runtime" / rel, core / rel)]
        inside[name], original[name] = map(str, variants[0])
    command = """
import json,os
from odoo.modules.module import get_module_path,get_manifest
env.cr.rollback()
env.cr.execute('SET TRANSACTION READ ONLY')
installed=env['ir.module.module'].search([('state','=','installed')])
assert set(installed.mapped('name'))==set(expected)
facts={}
for m in installed:
    assert os.path.samefile(get_module_path(m.name),expected[m.name])
    spec=get_manifest(m.name)
    assert (m.latest_version,m.license)==(spec['version'],spec['license'])
    facts[m.name]=[spec['version'],spec['license']]
print('RESULT='+json.dumps(facts))
env.cr.rollback()
"""
    scope = SimpleNamespace(database=FG, output=FG_RUNTIME, sealed=SOURCE_ARCHIVE)
    values = decode(run_fiscal_shell(launcher, scope, "freeze-final-providers", "expected=" + repr(inside) + "\n" + command))
    require(values == modules, "actual-source-registry-drift")
    return {n: [original[n], *values[n]] for n in modules}


def freeze():
    sys.path.insert(0, str(CHECKS))
    from guard_sys_original_catalogue import checkpoint
    odoo = qualified_odoo

    capacity(FG, INTENDED_RECOVERY)
    document = AUX / "document-admission.json"
    accepted = json.loads(document.read_bytes())
    require(accepted["database"] == FG and accepted["financial"]["exact_qualified_results"] and len(accepted["guarded_loads"]) == 4
            and accepted["document"]["http"]["recipient_granted"]["recipient"] == 200, "document-and-payroll-flows-required")
    reports = {"document-admission.json": document, "invoices.json": FG_RUNTIME / "invoice-pdf.json",
               "exports.json": FG_RUNTIME / "release-export-comparison.json",
               "final-storage.json": FG_RUNTIME / "combined-workflows-storage.json"}
    pdf, export, storage = [json.loads(reports[k].read_bytes()) for k in ("invoices.json", "exports.json", "final-storage.json")]
    require(len(pdf["printed"]) == 4 and export["pairs"] == 24 and export["matches"] and export["originals_preserved"] and
            not storage["covered_table_changes"] and not storage["relaxed_original_required_columns"] and
            storage["guard_count"] == 40, "final-fiscal-acceptance-required")
    catalogue = checkpoint(FG, "freeze_verified_product", "before")
    reports["original-schema.json"] = FG_RUNTIME / "catalogue" / catalogue
    modules = check_modules(FG)
    require(len(modules) == 192, "expected-192-final-providers")
    fiscal_profile = next(FG_RUNTIME / name for name in ("print-profile", "tested-profile", "profile")
                         if (FG_RUNTIME / name).is_dir())
    providers = active_sources(modules, odoo, fiscal_profile)
    OUT.mkdir(exist_ok=True, mode=0o750)
    service = pwd.getpwnam("odoo")
    os.chown(OUT, 0, service.pw_gid)
    OUT.chmod(0o750)
    source_store = FG_RUNTIME / "data/filestore" / FG
    catalog = object_catalog(attachments(FG, query)["references"])
    before = inventory(source_store, catalog)
    core = SOURCE_ARCHIVE / "runtime"
    args = SimpleNamespace(source_data=FG_RUNTIME / "data", release=ORIGIN / "revision61/release.tar", release_sha256=PAYROLL_SHA,
                           target=INTENDED_RECOVERY, runtime=core, addons=[], allow_forward_sequences_on_source=False)
    require(digest(args.release) == PAYROLL_SHA, "changed-payroll-release")
    frozen, proof, _, _ = package(args, OUT, FG, modules, effective_providers=providers)
    require(not proof["forward_manifests_on_source"] and proof["runtime"]["providers"] == 192 and
            proof["effective_licenses"] == dict(Counter(v[1] for v in modules.values())), "fiscal-source-manifests-differ")
    sealed = OUT / "sealed"
    for name, (source, expected) in ORIGINALS.items():
        require(digest(source) == expected, "original-supplier-package-mismatch:" + name)
        dst = sealed / name
        if not dst.exists():
            shutil.copyfile(source, dst)
        require(digest(dst) == expected, "sealed-supplier-package-mismatch:" + name)
    for name, source in reports.items():
        dst = OUT / name
        if not dst.exists():
            shutil.copyfile(source, dst)
        require(digest(dst) == digest(source), "frozen-functional-or-schema-evidence-differs")
    physical = physical_bundle(sealed, before, catalog, proof["sql_sha256"], source_store, INTENDED_RECOVERY)
    restore_files(OUT / "data", FG, sealed, prepare_runtime=True)
    verify_same(frozen, full_snapshot(FG))
    hidden = [core, FG_RUNTIME / "data", AUX / "documents/addons", *(FG_RUNTIME / name for name in ("profile","pinned","employee-profile"))]
    expected_document = [accepted["document"][k] for k in ("payslip", "document", "attachment", "bytes", "same_pdf_sha256")]
    first = open_as_user(OUT, FG, service, 1, hidden, expected_document)
    require(first["active"] == 192 and first["source_directories_hidden"] and first["read_only"], "cold-capsule-registry-drift")
    verify_same(frozen, full_snapshot(FG))
    require(first == open_as_user(OUT, FG, service, 2, hidden, expected_document), "cold-capsule-reboot-differs")
    verify_same(frozen, full_snapshot(FG))
    last = checkpoint(FG, "freeze_verified_product", "after")
    reports["final-schema.json"] = FG_RUNTIME / "catalogue" / last
    final_schema = OUT / "final-schema.json"
    if not final_schema.exists():
        shutil.copyfile(reports["final-schema.json"], final_schema)
    require(digest(final_schema) == digest(reports["final-schema.json"]), "cold-boot-catalogue-drift")
    result = {"database": FG, "source_sql_sha256": proof["sql_sha256"], "runtime": proof["runtime"],
              "effective_licenses": proof["effective_licenses"], "installed": len(modules), "physical": physical,
              "rows": proof["rows"], "counts": proof["counts"], "filestore_archive_sha256": proof["archive_sha256"],
              "original_release_archives": {"original-release.tar": PAYROLL_SHA, **{k:v[1] for k,v in ORIGINALS.items()}},
              "receipts": {n:digest(OUT / n) for n in reports}, "final_catalogue": last,
              "read_only_cold_boots_on_existing_database": 2, "cold_boot": first,
              "post_boot_database_and_sequence_snapshot_identical": True}
    save(OUT / "final-custody.json", result)


if __name__ == "__main__":
    os.umask(0o077)
    with open(LOCK, "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        freeze()
