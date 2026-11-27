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
    check(hash_file(manifest_file) == expected and set(manifest) == set(ARCHIVE_FILES), "source-checkpoint-expectation")
    for name, record in manifest.items():
        entry = folder / name
        check(entry.is_file() and entry.stat().st_size == record["bytes"] and hash_file(entry) == record["sha256"],
              "source-checkpoint-member:" + name)
    proof = read_json(folder / "backup.json")
    physical = read_json(folder / "filestore-physical.json")
    check(proof["source"] == physical["source"] and proof["sql_sha256"] == physical["sql_sha256"] ==
          manifest["source.dump"]["sha256"], "source-sql-identity")
    check(proof["runtime"]["providers"] == len(read_json(folder / "effective-providers.json")) == 190,
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
    return {"sql_sha256": proof["sql_sha256"], "source_cohort_manifest_sha256": expected,
            "verified_runtime_files": len(members), "verified_filestore_files": len(tree), "payroll_release_files": len(payroll)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.folder, args.manifest_sha256), indent=2))
