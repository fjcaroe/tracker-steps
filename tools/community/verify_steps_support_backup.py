"""Authenticate the H3 checkpoint and rebuild its exact filestore from the R archives and the H3 difference."""
import argparse
import ast
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

from verify_converted_backup import check, hash_file, package_manifest, read_json
from verify_steps_support_suite import PACKAGES


BASE_MANIFEST = "d45baa7b5c4894a31739d395b61a88f9c11a71b3edb54ecf414383b29296d3d9"
ACCEPTANCE = "7bbee05ec1426bc722570ff57a87824c130ac2ffbf1f210e5ff49b9e8d6a6c78"
SOURCE = "COMMUNITY_STEPS_CRM_SUPPORT_20261127U44H3"
SUCCESSOR = "COMMUNITY_STEPS_CRM_INTEGRATED_20261127U46A"
FILES = {"source.dump", "snapshot.json.gz", "sql-objects.json.gz", "filestore.json.gz", "filestore-delta.tar",
         "providers.json", "acceptance.json", *(name + ".tar" for name in PACKAGES)}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def strong(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def compressed(folder, name):
    return json.loads(gzip.decompress((folder / name).read_bytes()))


def base_parts(base):
    check(hash_file(base / "custody-manifest.json") == BASE_MANIFEST and
          package_manifest(base) == read_json(base / "custody-manifest.json"), "base-R-custody-drift")
    return base / "sealed" if (base / "sealed").is_dir() else base


def file_archive(path, expected=None, destination=None, selection=None):
    actual = {}
    with tarfile.open(path, "r|") as archive:
        for member in archive:
            match = re.fullmatch(r"(checklist/)?([0-9a-f]{2})/([0-9a-f]{40})", member.name)
            check(member.isfile() and match and match[2] == match[3][:2] and member.name not in actual,
                  "invalid-store-entry")
            with archive.extractfile(member) as stream:
                short, long = hashlib.sha1(), hashlib.sha256()
                saved = None
                if destination and member.name in selection:
                    target = destination / member.name
                    check(target.resolve().is_relative_to(destination.resolve()), "invalid-output-path")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    saved = target.open("xb")
                try:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        short.update(chunk)
                        long.update(chunk)
                        if saved:
                            saved.write(chunk)
                finally:
                    if saved:
                        saved.close()
            check(match[1] or short.hexdigest() == match[3], "invalid-content-address")
            actual[member.name] = [member.size, long.hexdigest()]
    if expected is not None:
        check(actual == expected, "archive-member-hash-drift")
    return actual


def verify(base, folder, expected_sha, destination=None):
    base = base_parts(base)
    check(hash_file(folder / "checkpoint.json") == expected_sha, "H3-checkpoint-digest")
    proof = read_json(folder / "checkpoint.json")
    check(proof["source"] == SOURCE and proof["base_manifest"] == BASE_MANIFEST
          and proof["acceptance"] == ACCEPTANCE and set(proof["files"]) == FILES, "H3-checkpoint-identity")
    for name, (size, sha) in proof["files"].items():
        path = folder / name
        check(path.is_file() and not path.is_symlink() and path.stat().st_size == size and hash_file(path) == sha,
              "checkpoint-piece:" + name)
    check(proof["files"]["acceptance.json"][1] == ACCEPTANCE, "wrong-functional-acceptance")
    sql = compressed(folder, "snapshot.json.gz")
    check(proof["tables"] == len(sql["public_tables"]) and proof["sequences"] == len(sql["sequence_values"])
          and proof["rows"] == sum(v[0] for v in sql["public_tables"].values()) and
          proof["schema_objects"] == len(compressed(folder, "sql-objects.json.gz")), "SQL-snapshot-shape")
    providers = read_json(folder / "providers.json")
    original = read_json(base / "effective-providers.json")
    check(providers.keys() == original.keys() | PACKAGES.keys() and len(providers) == 162, "active-provider-set")
    for name, facts in original.items():
        check(providers[name] == facts[1:], "original-provider-version")
    for name, (sha, count) in PACKAGES.items():
        package = folder / (name + ".tar")
        check(hash_file(package) == sha, "support-provider-release-drift")
        with tarfile.open(package) as archive:
            items = archive.getmembers()
            check(len(items) == count == len({m.name for m in items}) and all(m.isfile() and
                  PurePosixPath(m.name).parts[0] == name and ".." not in PurePosixPath(m.name).parts for m in items),
                  "support-package-members")
            manifest = ast.literal_eval(archive.extractfile(name + "/__manifest__.py").read().decode())
            check([manifest["version"], manifest["license"]] == providers[name] == ["18.0.1.0.2", "LGPL-3"],
                  "effective-support-manifest")
    tree = compressed(folder, "filestore.json.gz")
    changed = set(proof["changed_files"])
    check(changed <= tree.keys() and strong(tree) == proof["tree_sha256"], "H3-tree-manifest")
    if destination:
        check(destination.is_dir() and not destination.is_symlink() and not any(destination.iterdir()), "empty-store-required")
    common = tree.keys() - changed
    old = file_archive(base / "filestore.tar", destination=destination, selection=common)
    extra = file_archive(base / "filestore-extra.tar", destination=destination, selection=common)
    check(old.keys().isdisjoint(extra), "overlapping-original-archives")
    old.update(extra)
    check(strong(old) == read_json(base / "filestore-physical.json")["tree_sha256"] and
          {k for k, v in tree.items() if old.get(k) != v} == changed and
          sorted(old.keys() - tree.keys()) == proof["removed_files"], "storage-difference-drift")
    file_archive(folder / "filestore-delta.tar", {k: tree[k] for k in changed}, destination, changed)
    if destination:
        rebuilt = {p.relative_to(destination).as_posix(): [p.stat().st_size, hash_file(p)]
                   for p in destination.rglob("*") if p.is_file()}
        check(rebuilt == tree, "rebuilt-filestore-drift")
    return {"source": SOURCE, "source_sql_sha256": proof["files"]["source.dump"][1], "checkpoint_sha256": expected_sha,
            "tables": proof["tables"], "rows": proof["rows"], "sequences": proof["sequences"],
            "providers": len(providers), "physical_files": len(tree), "delta_files": len(changed),
            "removed_files": len(proof["removed_files"]), "schema_sha256": proof["schema_sha256"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", type=Path)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--rebuild-filestore", type=Path, help="An existing empty private directory")
    args = parser.parse_args()
    print(json.dumps(verify(args.base, args.folder, args.sha256, args.rebuild_filestore), indent=2))
