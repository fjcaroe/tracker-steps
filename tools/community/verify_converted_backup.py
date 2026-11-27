"""Verify the converted SQL, complete filestore and Community code archive without Odoo or PostgreSQL."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile


def check(condition, message):
    if not condition:
        raise ValueError(message)


def hash_file(path):
    with path.open("rb") as handle:
        return stream_hashes(handle)[1]


def stream_hashes(handle):
    short, strong = hashlib.sha1(), hashlib.sha256()
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        short.update(chunk)
        strong.update(chunk)
    return short.hexdigest(), strong.hexdigest()


def read_json(path):
    return json.loads(path.read_bytes())


ARCHIVE_FILES = (
    "backup.json", "source.dump", "filestore.tar", "runtime.tar.gz", "runtime-members.json",
    "effective-providers.json", "source-snapshot.json.gz", "original-release.tar",
    "original-release-files.sha256", "filestore-extra.tar", "filestore-physical.json",
)


def package_manifest(folder):
    sealed = folder / "sealed" if (folder / "sealed").is_dir() else folder
    paths = [sealed / name for name in ARCHIVE_FILES] + [folder / "restore-proof.json", folder / "schema-proof.json"]
    return {item.name: {"bytes": item.stat().st_size, "sha256": hash_file(item)} for item in paths}


def verify(folder, receipt_hash, manifest_hash=None):
    if manifest_hash:
        manifest = folder / "custody-manifest.json"
        check(hash_file(manifest) == manifest_hash, "independent-custody-manifest-digest")
        check(read_json(manifest) == package_manifest(folder), "portable-package-member-drift")
    source = folder / "sealed" if (folder / "sealed").is_dir() else folder
    receipt = folder / "restore-proof.json"
    check(hash_file(receipt) == receipt_hash, "restore-receipt-digest")
    proof, backup = read_json(receipt), read_json(source / "backup.json")
    physical = read_json(source / "filestore-physical.json")
    structure = read_json(folder / "schema-proof.json")
    check(proof["full_post_boot_match"] and proof["source_unchanged"] and proof["checked_boots"] == 2 and
          proof["role_probe"]["source_directories_hidden"], "required-cold-boot-evidence")
    check(backup["sql_sha256"] == proof["sql_sha256"] == physical["sql_sha256"], "sql-backup-identity")
    schemas = [structure[label + "_schema_sha256"] for label in ("archive", "source", "restored")]
    check(len(set(schemas)) == 1 and re.fullmatch("[a-f0-9]{64}", schemas[0]) and
          structure["source_types"] == structure["restored_types"], "schema-proof-drift")
    for filename, expected in {
        "source.dump": proof["sql_sha256"], "original-release.tar": backup["release_sha256"],
        "filestore.tar": proof["archive_sha256"], "filestore-extra.tar": physical["extra_archive_sha256"],
        "runtime.tar.gz": proof["runtime"]["archive_sha256"],
        "runtime-members.json": proof["runtime"]["manifest_sha256"],
    }.items():
        check(hash_file(source / filename) == expected, filename + "-digest")
    members = read_json(source / "runtime-members.json")
    providers = read_json(source / "effective-providers.json")
    check(len(providers) == proof["role_probe"]["active"] == proof["runtime"]["providers"], "runtime-provider-count")
    for name in providers:
        path = "odoo/addons/base/__manifest__.py" if name == "base" else f"addons/{name}/__manifest__.py"
        check(path in members, "provider-manifest-missing")
    pending = set(members)
    with tarfile.open(source / "runtime.tar.gz", "r|gz") as runtime:
        for entry in runtime:
            path = PurePosixPath(entry.name)
            check(entry.isfile() and not path.is_absolute() and ".." not in path.parts and entry.name in pending,
                  "unexpected-runtime-member")
            pending.remove(entry.name)
            size, strong, mode = members[entry.name]
            with runtime.extractfile(entry) as incoming:
                check(entry.size == size and entry.mode == mode and stream_hashes(incoming)[1] == strong,
                      "runtime-content-drift")
    check(not pending and len(members) == proof["runtime"]["files"], "incomplete-runtime")
    tree = {}
    counts = []
    for name, extra in (("filestore.tar", False), ("filestore-extra.tar", True)):
        count = 0
        with tarfile.open(source / name, "r|") as storage:
            for entry in storage:
                match = re.fullmatch(r"(checklist/)?([0-9a-f]{2})/([0-9a-f]{40})", entry.name)
                check(entry.isfile() and match and match[2] == match[3][:2] and entry.name not in tree,
                      "unexpected-filestore-member")
                with storage.extractfile(entry) as incoming:
                    short, strong = stream_hashes(incoming)
                if not match[1]:
                    check(short == match[3], "original-content-address-drift")
                tree[entry.name] = [entry.size, strong]
                if extra:
                    check(tree[entry.name] == physical["extras"].get(entry.name), "supplemental-content-drift")
                else:
                    check(not match[1], "unexpected-marker-in-referenced-archive")
                count += 1
        counts.append(count)
    tree_hash = hashlib.sha256(json.dumps(tree, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    check(tree_hash == physical["tree_sha256"] and len(tree) == physical["all_files"], "physical-filestore-drift")
    check(counts == [proof["restored_filestore_objects"], len(physical["extras"])], "filestore-counts")
    return {"tables": proof["counts"]["public_tables"], "rows": proof["rows"], "providers": len(providers),
            "runtime_files": len(members), "referenced_objects": counts[0], "supplemental_files": counts[1],
            "all_filestore_files": len(tree), "receipt_sha256": receipt_hash}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--receipt-sha256")
    mode.add_argument("--write-manifest", action="store_true",
                      help="Seal the 13 custody files after SQL, role, physical store and schema verification")
    parser.add_argument("--manifest-sha256", help="Independently supplied digest of the complete custody manifest")
    args = parser.parse_args()
    if args.write_manifest:
        contents = package_manifest(args.folder)
        verify(args.folder, contents["restore-proof.json"]["sha256"])
        destination = args.folder / "custody-manifest.json"
        if destination.exists():
            check(read_json(destination) == contents, "previous-custody-manifest-drift")
        else:
            with destination.open("x", encoding="utf-8") as handle:
                json.dump(contents, handle, indent=2, sort_keys=True)
        print(hash_file(destination))
    else:
        print(json.dumps(verify(args.folder, args.receipt_sha256, args.manifest_sha256), indent=2))
