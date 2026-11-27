"""Verify the portable source checkpoint used jointly by the SyS payroll and document restorations."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

from verify_converted_backup import ARCHIVE_FILES, check, hash_file, read_json, stream_hashes


FISCAL_RECEIPTS = {"document-admission.json", "invoices.json", "exports.json", "final-storage.json",
                   "original-schema.json", "final-schema.json"}
FISCAL_PACKAGES = {"original-fiscal-release.tar": (187, 6), "original-employee-release.tar": (218, 1),
                   "original-policy-release.tar": (200, 2), "original-documents-release.tar": (20, 2)}


def verify_final_product(folder, manifest, members, proof):
    accepted = read_json(folder / "final-custody.json")
    check(accepted["source_sql_sha256"] == proof["sql_sha256"] and accepted["runtime"] == proof["runtime"]
          and accepted["read_only_cold_boots_on_existing_database"] == 2 and
          accepted["post_boot_database_and_sequence_snapshot_identical"] and accepted["cold_boot"]["read_only"] and
          accepted["cold_boot"]["source_directories_hidden"] and not proof["forward_manifests_on_source"],
          "final-cold-boot-or-registry-evidence")
    check(accepted["receipts"] == {n: manifest[n]["sha256"] for n in FISCAL_RECEIPTS}, "final-receipt-checksum")
    doc = read_json(folder / "document-admission.json")
    exports = read_json(folder / "exports.json")
    check(doc["financial"]["exact_qualified_results"] and len(doc["guarded_loads"]) == 4 and
          doc["document"]["http"]["recipient_granted"]["recipient"] == 200 and
          exports["matches"] and exports["pairs"] == 24 and exports["originals_preserved"] and
          len(read_json(folder / "invoices.json")["printed"]) == 4, "fiscal-payroll-document-integration-evidence")
    code_versions = read_json(folder / "effective-providers.json")
    licenses = {}
    for _, _, license_ in code_versions.values():
        licenses[license_] = licenses.get(license_, 0) + 1
    check(set(licenses) <= {"AGPL-3", "LGPL-3", "GPL-3"} and len(code_versions) == 192 and
          licenses == proof["effective_licenses"] == proof["database_licenses"] == accepted["effective_licenses"],
          "effective-licenses-in-final-registry")
    private_file = doc["document"]
    cold = accepted["cold_boot"]
    cold_file = cold["original_library_payslip"]
    check(cold_file["same_document_and_payslip"] and cold_file["ordinary_manager"] == private_file["manager"]
          and cold_file["sha256"] == private_file["same_pdf_sha256"] and cold_file["bytes"] == private_file["bytes"]
          and cold["payroll_pdf"]["different_company_denied"] and cold["payroll_pdf"]["public_denied"],
          "restored-ordinary-file-and-denials")
    sections = {"columns", "constraints", "indexes", "invoice_layouts", "relation_owner_and_acl",
                "sequence_definitions", "sequence_owned_by", "views"}
    for name in ("original-schema.json", "final-schema.json"):
        schema = read_json(folder / name)
        check(len(schema["required"]) == 21 and all(schema["required"].values()) and
              schema["sections"].keys() == sections and all(not s["missing"] and not s["changed"] for s in schema["sections"].values()), "original-fiscal-schema-drift")
    for filename, (count, module_count) in FISCAL_PACKAGES.items():
        check(accepted["original_release_archives"][filename] == manifest[filename]["sha256"], "supplier-archive-checksum")
        archived = {}
        with tarfile.open(folder / filename, "r:") as bundle:
            for member in bundle:
                if member.isdir():
                    continue
                path = member.name.removeprefix("./")
                key = path if filename == "original-documents-release.tar" else "addons/" + path
                check(member.isfile() and key not in archived and ".." not in PurePosixPath(key).parts, "supplier-release-member")
                with bundle.extractfile(member) as incoming:
                    archived[key] = [member.size, stream_hashes(incoming)[1]]
        providers = {k.split("/")[1] for k in archived}
        actual = {k: v[:2] for k, v in members.items() if k.startswith("addons/") and k.split("/")[1] in providers}
        check(len(archived) == count and len(providers) == module_count and actual == archived, "effective-fiscal-provider-drift")


def verify(folder, expected):
    manifest_file = folder / "verified-local-members.json"
    manifest = read_json(manifest_file)
    combined = "original-documents-release.tar" in manifest
    extras = {"original-documents-release.tar", "fiscal-source.json", "combined-product-proof.json"} if combined else set()
    final_fiscal = "final-custody.json" in manifest
    if final_fiscal:
        extras = set(FISCAL_PACKAGES) | FISCAL_RECEIPTS | {"final-custody.json"}
    check(hash_file(manifest_file) == expected and set(manifest) == set(ARCHIVE_FILES) | extras,
          "source-checkpoint-expectation")
    for name, record in manifest.items():
        entry = folder / name
        check(entry.is_file() and entry.stat().st_size == record["bytes"] and hash_file(entry) == record["sha256"],
              "source-checkpoint-member:" + name)
    proof = read_json(folder / "backup.json")
    physical = read_json(folder / "filestore-physical.json")
    check(proof["source"] == physical["source"] and proof["sql_sha256"] == physical["sql_sha256"] ==
          manifest["source.dump"]["sha256"], "source-sql-identity")
    expected_source = "COMMUNITY_SYS_PREVIRED_COHORT_20261127U43C" if combined else "COMMUNITY_SYS_PREVIRED_COHORT_20261126U42L"
    if final_fiscal:
        expected_source = "COMMUNITY_SYS_PREVIRED_MODULES_20261127U44FG"
    check(proof["source"] == expected_source, "source-cohort-identity")
    count = 192 if combined else 190
    check(proof["runtime"]["providers"] == len(read_json(folder / "effective-providers.json")) == count,
          "source-provider-count")
    members = read_json(folder / "runtime-members.json")
    pending = set(members)
    with tarfile.open(folder / "runtime.tar.gz", "r|gz") as code:
        for entry in code:
            check(entry.isfile() and entry.name in pending, "unexpected-runtime-member")
            pending.remove(entry.name)
            with code.extractfile(entry) as payload:
                check([entry.size, stream_hashes(payload)[1], entry.mode] == members[entry.name],
                      "different-runtime-member")
    check(not pending, "missing-runtime-members")
    tree = {}
    for name in ("filestore.tar", "filestore-extra.tar"):
        with tarfile.open(folder / name, "r|") as archive:
            for entry in archive:
                key = entry.name
                check(entry.isfile() and key not in tree, "unexpected-filestore-member")
                with archive.extractfile(entry) as payload:
                    short, full = stream_hashes(payload)
                check(key.startswith("checklist/") or short == PurePosixPath(key).name, "filestore-address-differs")
                tree[key] = [entry.size, full]
                if name == "filestore-extra.tar":
                    check(tree[key] == physical["extras"].get(key), "supplemental-object-differs")
    serial = json.dumps(tree, sort_keys=True, separators=(",", ":")).encode()
    check(hashlib.sha256(serial).hexdigest() == physical["tree_sha256"] and len(tree) == physical["all_files"],
          "original-physical-store-differs")
    payroll = {}
    for line in (folder / "original-release-files.sha256").read_text().splitlines():
        checksum, path = line.split("  ", 1)
        key = path.removeprefix("./")
        check(key not in payroll, "duplicate-payroll-manifest-member")
        payroll[key] = checksum
    pending = set(payroll)
    with tarfile.open(folder / "original-release.tar", "r:") as archive:
        for entry in archive:
            if entry.isdir():
                continue
            key = entry.name.removeprefix("./")
            check(entry.isfile() and key in pending, "unknown-qualified-payroll-member")
            pending.remove(key)
            with archive.extractfile(entry) as payload:
                check(stream_hashes(payload)[1] == payroll[key], "qualified-payroll-member-differs")
    source_modules = {name.split("/")[0] for name in payroll}
    actual = {name.removeprefix("addons/"): value[1] for name, value in members.items()
              if name.startswith("addons/") and name.split("/")[1] in source_modules}
    check(not pending and len(payroll) == 133 and len(source_modules) == 7, "original-payroll-release-incomplete")
    if final_fiscal:
        transition = "step_payroll_engine_transition/"
        changed = {name for name in payroll.keys() & actual.keys() if actual[name] != payroll[name]}
        check(not (payroll.keys() - actual.keys()) and
              changed == {transition + "__manifest__.py", transition + "security/rules.xml"} and
              actual.keys() - payroll.keys() == {transition + "security/sys_preserved_access.xml"} and
              manifest["original-release.tar"]["sha256"] == "547c89989b796475cbb46075992f4008c10d23f7a50bbf450f0941192e81fc07" and
              manifest["original-fiscal-release.tar"]["sha256"] == "ca9180cdd5d3be9b5e69073d83171760cef34b22b07ae0a7cb38940cbd63ce37",
              "qualified-fiscal-supersession-differs")
        # verify_final_product also matches this entire installed module to the independently qualified fiscal TAR.
    else:
        check(actual == payroll, "effective-payroll-tree-differs")
    docs = {}
    if final_fiscal:
        verify_final_product(folder, manifest, members, proof)
    elif combined:
        receipt = read_json(folder / "fiscal-source.json")
        check(receipt["sql_sha256"] == proof["sql_sha256"] and receipt["functional_source_preserved"] and
              receipt["source_functional_receipt_sha256"] == manifest["combined-product-proof.json"]["sha256"],
              "combined-test-receipt-differs")
        admitted = read_json(folder / "combined-product-proof.json")
        check(admitted["payroll"]["exact_qualified_results"] and admitted["document"]["http"]["recipient_granted"]["recipient"] == 200,
              "missing-functional-acceptance")
        archive_sha = manifest["original-documents-release.tar"]["sha256"]
        check(archive_sha == receipt["original_documents_release_sha256"] == admitted["document_release_sha256"],
              "document-package-identity")
        with tarfile.open(folder / "original-documents-release.tar", "r:") as archive:
            for item in archive:
                if item.isdir():
                    continue
                key = item.name
                check(item.isfile() and key.startswith(("addons/step_document_library/", "addons/step_document_library_portal/"))
                      and key not in docs, "unexpected-document-provider-member")
                with archive.extractfile(item) as payload:
                    docs[key] = [item.size, stream_hashes(payload)[1]]
        active_docs = {name: value[:2] for name, value in members.items()
                       if name.startswith(("addons/step_document_library/", "addons/step_document_library_portal/"))}
        check(len(docs) == receipt["additional_document_files"] == 20 and docs == active_docs,
              "effective-document-addons-differ")
    return {"sql_sha256": proof["sql_sha256"], "source_cohort_manifest_sha256": expected,
            **({"effective_payroll_tree_files": len(actual), "qualified_fiscal_changes_to_payroll_files": 2,
                "qualified_fiscal_additions_to_payroll_files": 1} if final_fiscal else {}),
            "providers": count, "document_release_files": 20 if final_fiscal else len(docs),
            "verified_runtime_files": len(members), "verified_filestore_files": len(tree), "payroll_release_files": len(payroll)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.folder, args.manifest_sha256), indent=2))
