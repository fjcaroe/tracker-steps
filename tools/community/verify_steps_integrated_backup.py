"""Verify the final integrated Steps checkpoint offhost and rebuild its storage from the signed R/H3 chain."""
import argparse
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

from verify_converted_backup import check, hash_file, read_json, stream_hashes
from verify_steps_support_backup import (SUCCESSOR, compressed, file_archive, strong, verify as verify_support)
from verify_steps_support_portal_http import compare


H3_SHA = "4d50b17bdcf4cbe781c01569cbc12632e2dc114273497b56d4258ee298136dd1"
RESTORED = "COMMUNITY_STEPS_CRM_RECOVERY_20261127U46B"
FISCAL = "step_cl_invoice_status_history"
FISCAL_SHA = "8c7cf3cc764d92740db4549b395ddc27b126ab71596c9e2c7744a830f559cf2f"
PORTAL = "step_helpdesk_tickets_portal"
PORTAL_SHA = "23d61b9f8c3ed1f4e9c59f238fe38b8ff45d75b41c3035acd1dac1fc7920d68a"
WORKFLOW_SHA = "37eb3501c72509dd7e954a2fdd839b145ad8499e5a60893db3531b4857c09bc8"
INVOICES = "U46AFinalFiscal-steps-invoice-text-integrated.json"
OFFICIAL = {
    "l10n_cl": ("18.0.3.1", 51, "9d7de7aa6636f7f72a616171412ac0ff53bf7d6ebeab117ff03cb954e978b3b0"),
    "l10n_latam_invoice_document": ("18.0.1.0", 25, "c6b2892e5cd07f111cec03798ec3cfca117dd30340d342c28eff72c3c929d2a7"),
}
PIECES = {"source.dump", "snapshot.json.gz", "sql-objects.json.gz", "providers.json", "filestore.json.gz",
          "filestore-delta.tar", "official-fiscal.tar", "fiscal-release.tar", "portal-release.tar", "functional-evidence.tar"}


def module_archives(folder, providers, package_sha, destination=None):
    check(hash_file(folder / "fiscal-release.tar") == package_sha == FISCAL_SHA, "qualified-fiscal-package-sha256")
    check(hash_file(folder / "portal-release.tar") == PORTAL_SHA, "stable-ticket-release-sha256")
    for package, expected in (("fiscal-release.tar", {FISCAL}), ("official-fiscal.tar", set(OFFICIAL)),
                              ("portal-release.tar", {PORTAL})):
        files = {name: {} for name in expected}
        manifests = {}
        with tarfile.open(folder / package, "r|") as archive:
            for member in archive:
                path = PurePosixPath(member.name)
                check(member.isfile() and not path.is_absolute() and len(path.parts) >= 2 and
                      ".." not in path.parts and path.parts[0] in files, "invalid-fiscal-source")
                name, key = path.parts[0], "/".join(path.parts[1:])
                check(key not in files[name], "duplicate-fiscal-source")
                data = archive.extractfile(member).read()
                files[name][key] = hashlib.sha256(data).hexdigest()
                if key == "__manifest__.py":
                    manifests[name] = ast.literal_eval(data.decode())
                if destination is not None:
                    out = destination / member.name
                    check(out.resolve().is_relative_to(destination.resolve()), "invalid-fiscal-output")
                    out.parent.mkdir(parents=True, exist_ok=True)
                    with out.open("xb") as saved:
                        saved.write(data)
                    out.chmod(0o644)
        for name, items in files.items():
            version = manifests[name]["version"]
            version = version if version.startswith("18.0.") else "18.0." + version
            check([version, manifests[name]["license"]] == providers[name] and manifests[name]["license"] == "LGPL-3",
                  "fiscal-version-or-license-drift")
            if name in OFFICIAL:
                check((version, len(items), strong(items)) == OFFICIAL[name], "official-provider-tree-differs")
            elif name == FISCAL:
                check(version == "18.0.1.0.3" and len(items) == 6, "custom-fiscal-release-files")
            else:
                check(version == "18.0.1.0.3" and len(items) == 7, "stable-ticket-release-files")


def verify(base, h3, folder, sha, destination=None):
    initial = verify_support(base, h3, H3_SHA, destination)
    check(hash_file(folder / "checkpoint.json") == sha, "integrated-checkpoint-sha256")
    proof = read_json(folder / "checkpoint.json")
    check(proof["source"] == SUCCESSOR and proof["parent"] == H3_SHA and set(proof["files"]) == PIECES,
          "wrong-Steps-branch")
    for name, (size, checksum) in proof["files"].items():
        path = folder / name
        check(path.is_file() and not path.is_symlink() and path.stat().st_size == size and hash_file(path) == checksum,
              "integrated-checkpoint-piece:" + name)
    frozen = compressed(folder, "snapshot.json.gz")
    check(proof["rows"] == sum(v[0] for v in frozen["public_tables"].values()) and
          proof["tables"] == len(frozen["public_tables"]) and proof["sequences"] == len(frozen["sequence_values"]) and
          proof["schema_objects"] == len(compressed(folder, "sql-objects.json.gz")), "full-SQL-evidence")
    parent = read_json(h3 / "providers.json")
    parent[PORTAL] = ["18.0.1.0.3", "LGPL-3"]
    active = read_json(folder / "providers.json")
    check(initial["providers"] == len(parent) == 162 and len(active) == 165 and
          active.keys() == parent.keys() | OFFICIAL.keys() | {FISCAL} and all(active[n] == v for n, v in parent.items()),
          "unexpected-165-module-set")
    module_archives(folder, active, proof["fiscal_package_sha256"])
    checks = {}
    with tarfile.open(folder / "functional-evidence.tar", "r|") as records:
        pending = dict(proof["functional_evidence"])
        check(pending.get("workflow-acceptance.json") == WORKFLOW_SHA, "unknown-fiscal-functional-suite")
        for item in records:
            check(item.isfile() and PurePosixPath(item.name).name == item.name and item.name in pending,
                  "unrecognized-functional-evidence")
            stream = records.extractfile(item)
            if item.name == "workflow-acceptance.json":
                data = stream.read()
                observed = hashlib.sha256(data).hexdigest()
                suite = json.loads(data)
                check(suite["database"] == SUCCESSOR and suite["providers"] == 165 and
                      all(proof["functional_evidence"].get(k) == v for k, v in suite["receipts"].items()),
                      "functional-suite-children-missing")
            elif item.name in ("support-integrated.json", "support-original.json", "ticket-orders-acceptance.json"):
                data = stream.read()
                checks[item.name] = json.loads(data)
                observed = hashlib.sha256(data).hexdigest()
            else:
                observed = stream_hashes(stream)[1]
            check(observed == pending.pop(item.name), "functional-receipt-bytes")
        check(not pending and proof["functional_evidence"], "missing-functional-evidence")
    current = checks["support-integrated.json"]
    baseline = checks["support-original.json"]
    pages = checks["ticket-orders-acceptance.json"]
    check(current["modules"] == 165 and current["thread"] == baseline["thread"] and
          current["reference_sha256"] == proof["functional_evidence"]["support-original.json"] and
          compare(baseline["http"], current["http"], target=SUCCESSOR) == current["verified_http"] and
          pages["native_sha256"] == proof["functional_evidence"]["native-orders.json"] and
          pages["integrated_sha256"] == proof["functional_evidence"]["integrated-orders.json"] and
          pages["stable_complete_and_split_page_order"] == pages["native_complete_page_order"] and
          pages["plans"] == 3 and pages["page_sizes"] == [2,80], "support-or-pagination-acceptance-drift")
    tree, old = compressed(folder, "filestore.json.gz"), compressed(h3, "filestore.json.gz")
    changed = {k: v for k, v in tree.items() if old.get(k) != v}
    removed = sorted(old.keys() - tree.keys())
    check(strong(tree) == proof["tree_sha256"] and sorted(changed) == proof["changed_files"] and
          removed == proof["removed_files"], "integrated-store-difference")
    if destination:
        for name in set(removed) | (old.keys() & changed.keys()):
            path = destination / name
            check(path.resolve().is_relative_to(destination.resolve()) and hash_file(path) == old[name][1],
                  "unexpected-replacement-in-new-store")
            path.unlink()
    file_archive(folder / "filestore-delta.tar", changed, destination, changed)
    if destination:
        rebuilt = {p.relative_to(destination).as_posix(): [p.stat().st_size, hash_file(p)]
                   for p in destination.rglob("*") if p.is_file()}
        check(rebuilt == tree, "reconstructed-165-store-differs")
    return {"source": SUCCESSOR, "checkpoint_sha256": sha, "source_sql_sha256": proof["files"]["source.dump"][1],
            "rows": proof["rows"], "tables": proof["tables"], "sequences": proof["sequences"],
            "schema_sha256": proof["schema_sha256"], "schema_objects": proof["schema_objects"],
            "providers": len(active), "physical_files": len(tree), "changed_files": len(changed),
            "removed_files": len(removed), "qualified_evidence": len(proof["functional_evidence"])}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for item in ("base", "h3", "folder"):
        parser.add_argument(item, type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--rebuild-filestore", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.base, args.h3, args.folder, args.sha256, args.rebuild_filestore), indent=2))
