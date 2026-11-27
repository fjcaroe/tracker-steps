"""Verify the portable source checkpoint used jointly by the SyS payroll and document restorations."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

from verify_converted_backup import ARCHIVE_FILES, check, hash_file, read_json, stream_hashes


def verify(folder, expected):
    manifest_file = folder / "verified-local-members.json"
    manifest = read_json(manifest_file)
    combined = "original-documents-release.tar" in manifest
    extras = {"original-documents-release.tar", "fiscal-source.json", "combined-product-proof.json"} if combined else set()
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
    check(not pending and actual == payroll and len(payroll) == 133 and len(source_modules) == 7,
          "effective-payroll-tree-differs")
    docs = {}
    if combined:
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
            "providers": count, "document_release_files": len(docs),
            "verified_runtime_files": len(members), "verified_filestore_files": len(tree), "payroll_release_files": len(payroll)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.folder, args.manifest_sha256), indent=2))
