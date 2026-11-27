"""Retain unreferenced content and original garbage-collection markers in a sealed private filestore."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tarfile
import tempfile

from custody_sys_previred_filestore import attachments, digest, object_catalog
from restore_native_product_backup import query
from restore_sys_previred_pair import LOCK, require


def inventory(path, catalog):
    result = {}
    for p in path.rglob("*"):
        require(not p.is_symlink(), "unexpected-filestore-symlink")
        if not p.is_file():
            require(p.is_dir(), "unexpected-filestore-entry")
            continue
        key = p.relative_to(path).as_posix()
        item = re.fullmatch(r"(checklist/)?([a-f0-9]{2})/([a-f0-9]{40})", key)
        require(item and item[2] == item[3][:2], "unknown-filestore-file")
        if not item[1]:
            require(digest(p, "sha1") == item[3], "invalid-content-object")
        size = p.stat().st_size
        require(key not in catalog or catalog[key] == size, "unexpected-referenced-size")
        result[key] = [size, digest(p)]
    require(catalog.keys() <= result.keys(), "referenced-filestore-object-missing")
    return result


def restore_supplement(archive, extra, dest):
    seen = set()
    owner = dest.stat()
    with tarfile.open(archive, "r|") as bundle:
        for member in bundle:
            key = member.name
            require(member.isfile() and key in extra and key not in seen and member.size == extra[key][0],
                    "unexpected-supplemental-object")
            match = re.fullmatch(r"(checklist/)?([a-f0-9]{2})/([a-f0-9]{40})", key)
            require(match and match[2] == match[3][:2], "invalid-supplemental-object-name")
            seen.add(key)
            target = dest / key
            parent = target.parent
            parent.mkdir(parents=True, exist_ok=True)
            require(target.resolve() == target, "unexpected-supplemental-symlink")
            for ancestor in (parent, *parent.parents):
                if ancestor == dest:
                    break
                os.chown(ancestor, owner.st_uid, owner.st_gid)
            with bundle.extractfile(member) as incoming, tempfile.NamedTemporaryFile(dir=parent, delete=False) as added:
                tmp = Path(added.name)
                try:
                    shutil.copyfileobj(incoming, added)
                    added.flush()
                    require(digest(tmp) == extra[key][1], "supplemental-object-checksum")
                    if not target.exists():
                        os.chown(tmp, owner.st_uid, owner.st_gid)
                        os.link(tmp, target)
                    require(digest(target) == extra[key][1], "supplemental-target-drift")
                finally:
                    tmp.unlink(missing_ok=True)
    require(seen == extra.keys(), "supplemental-object-missing")


def complete(folder, source_store):
    proof = json.loads((folder / "restore-proof.json").read_text())
    source, restored = proof["source"], proof["target"]
    require(proof["full_post_boot_match"] and proof["checked_boots"] == 2 and
            re.fullmatch(r"COMMUNITY_SYS_PREVIRED_COHORT_[A-Z0-9_]+", source) and
            source_store.resolve() == source_store and source_store.name == source and
            source_store.is_relative_to("/opt/steps-validation") and source_store.parent.name == "filestore",
            "isolated-converted-source-required")
    rows = attachments(source, query)
    catalog = object_catalog(rows.pop("references"))
    require(rows == proof["attachments"], "sealed-attachment-rows-differ")
    dest = folder / "data/filestore" / restored
    require(restored.startswith("COMMUNITY_SYS_PREVIRED_RECOVERY_") and dest.resolve() == dest, "private-target-required")
    original = inventory(source_store, catalog)
    extra = {k: original[k] for k in sorted(original.keys() - catalog.keys())}
    work = folder / "sealed"
    archive = work / "filestore-extra.tar"
    if not archive.exists():
        with tempfile.TemporaryDirectory(dir=work) as temp:
            stage = Path(temp) / "filestore-extra.tar"
            with tarfile.open(stage, "x") as bundle:
                for key in extra:
                    bundle.add(source_store / key, arcname=key, recursive=False)
            os.link(stage, archive)
    restore_supplement(archive, extra, dest)
    require(inventory(dest, catalog) == original, "full-physical-filestore-differs")
    encoded = json.dumps(original, sort_keys=True, separators=(",", ":")).encode()
    result = {"source": source, "restored": restored, "sql_sha256": proof["sql_sha256"],
              "referenced_objects": len(catalog), "unreferenced_objects": sum(not k.startswith("checklist/") for k in extra),
              "checklist_markers": sum(k.startswith("checklist/") for k in extra),
              "supplemental_bytes": sum(v[0] for v in extra.values()), "all_files": len(original),
              "tree_sha256": hashlib.sha256(encoded).hexdigest(), "extra_archive_sha256": digest(archive), "extras": extra}
    (work / "filestore-physical.json").write_text(json.dumps(result, sort_keys=True, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k != "extras"}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("source_filestore", type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    with open(LOCK, "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        complete(args.folder, args.source_filestore)
