"""Freeze the tested 192-module SyS product before a separately authorized fiscal rehearsal."""
import fcntl
import gzip
import json
import os
from pathlib import Path
import shutil
import tarfile
from types import SimpleNamespace

from admit_sys_combined_documents import DATA, DOCUMENTS, PACKAGE, ROOT, SEALED, TARGET
from capture_sys_combined_source import DOCUMENT_SHA, ORIGIN, PAYROLL_SHA, capacity, physical_bundle
from complete_converted_filestore import inventory
from custody_sys_previred_filestore import attachments, digest, object_catalog
from restore_converted_sys_cohort import check_modules, full_snapshot, package, save, verify_same
from restore_native_product_backup import query
from restore_sys_previred_pair import LOCK, require

NEXT = "COMMUNITY_SYS_PREVIRED_MODULES_20261127U44FD"
OUTPUT = ROOT / "combined-checkpoint"


def freeze():
    accepted = ROOT / "combined-product-proof.json"
    evidence = json.loads(accepted.read_bytes())
    require(evidence["target"] == TARGET and evidence["installed"] == 192 and evidence["enterprise"] == 0 and
            evidence["payroll"]["exact_qualified_results"] and evidence["document"]["ordinary_payroll_and_attachment"] and
            evidence["document"]["http"]["recipient_granted"]["recipient"] == 200, "both-functional-paths-required")
    # Preserve the existing archival evidence. Reusing this copy for another fiscal
    # admission also requires every original SQL field contract to remain intact.
    original = json.loads(gzip.decompress((SEALED / 'source-snapshot.json.gz').read_bytes()))
    candidate = full_snapshot(TARGET)
    for section in ('columns', 'constraints', 'relation_owner_and_acl', 'sequence_definitions'):
        changed = sorted(key for key, value in original[section].items() if candidate[section].get(key) != value)
        require(not changed, 'original-SyS-schema-drift-before-fiscal-promotion:' + section + ':' + ','.join(changed))
    capacity()
    require(query("postgres", f"SELECT count(*) FROM pg_stat_activity WHERE datname='{NEXT}'") == "0",
            "next-test-copy-in-use")
    modules = check_modules(TARGET)
    require(len(modules) == 192, "combined-product-provider-drift")
    core = SEALED / "runtime"
    args = SimpleNamespace(source_data=DATA, release=ORIGIN / "revision61/release.tar", release_sha256=PAYROLL_SHA,
                           target=NEXT, runtime=core, addons=[DOCUMENTS / "addons", core / "addons", core / "odoo/addons"],
                           allow_forward_sequences_on_source=False)
    require(digest(args.release) == PAYROLL_SHA and digest(PACKAGE) == DOCUMENT_SHA,
            "qualified-package-differs")
    OUTPUT.mkdir(exist_ok=True, mode=0o700)
    catalog = object_catalog(attachments(TARGET, query)["references"])
    original = DATA / "filestore" / TARGET
    before = inventory(original, catalog)
    frozen, proof, _, _ = package(args, OUTPUT, TARGET, modules)
    verify_same(frozen, full_snapshot(TARGET))
    sealed = OUTPUT / "sealed"
    files = json.loads((sealed / "runtime-members.json").read_bytes())
    old = json.loads((SEALED / "runtime-members.json").read_bytes())
    require(all(files.get(k) == v for k, v in old.items()), "payroll-source-tree-differs")
    extra = files.keys() - old.keys()
    with tarfile.open(PACKAGE) as archive:
        added = set()
        for item in archive:
            if item.isdir():
                continue
            name = Path(item.name)
            require(item.isfile() and name.parts[0] == "addons" and name.parts[1] in
                    ("step_document_library", "step_document_library_portal") and name.as_posix() not in added,
                    "unexpected-document-release-member")
            added.add(name.as_posix())
            require(files[name.as_posix()][:2] == [item.size, digest(DOCUMENTS / name)],
                    "document-provider-file-differs")
        require(added == extra and len(added) == 20, "combined-provider-tree-differs")
    docs = sealed / "original-documents-release.tar"
    if not docs.exists():
        shutil.copyfile(PACKAGE, docs)
    require(digest(docs) == DOCUMENT_SHA, "second-product-release-differs")
    physical = physical_bundle(sealed, before, catalog, proof["sql_sha256"], original, NEXT)
    parent = json.loads((ROOT / "source-checkpoint.json").read_bytes())
    result = {"source": TARGET, "planned_restoration": NEXT, "original_payroll_source_sql": parent["sql"],
              "sql_sha256": proof["sql_sha256"], "filestore_sha256": proof["archive_sha256"],
              "runtime": proof["runtime"], "effective_licenses": proof["effective_licenses"], "physical": physical,
              "payroll_release_sha256": PAYROLL_SHA, "original_documents_release_sha256": DOCUMENT_SHA,
              "original_payroll_runtime_files": len(old), "additional_document_files": len(extra),
              "source_functional_receipt_sha256": digest(accepted), "combined_tables": len(frozen["public_tables"]),
              "combined_sequences": len(frozen["sequence_values"]), "combined_rows": proof["rows"],
              "functional_source_preserved": True}
    require(result["runtime"]["providers"] == 192 and result["effective_licenses"] == {"AGPL-3": 2, "LGPL-3": 190},
            "source-licensing-drift")
    save(OUTPUT / "fiscal-source.json", result)


if __name__ == "__main__":
    os.umask(0o077)
    with open(LOCK, "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        freeze()
