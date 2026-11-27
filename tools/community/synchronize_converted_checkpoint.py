"""Capture SQL and the full physical file inventory together and verify this checkpoint on a fresh private DB."""
import argparse
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import tarfile
import tempfile

from complete_converted_filestore import inventory
from custody_sys_previred_filestore import attachments, digest, object_catalog
from restore_converted_sys_cohort import check_modules, full_snapshot, open_as_user, save, source_sequence_advances, verify_same
from restore_native_product_backup import pg, query
from restore_sys_previred_pair import GIB, LOCK, require
from verify_converted_sql_schema import schema


def tree_hash(files):
    payload = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def write_archive(path, source_store, extra):
    with tarfile.open(path, "x") as archive:
        for name in sorted(extra):
            archive.add(source_store / name, arcname=name, recursive=False)


def checkpoint(primary, work, source_store, target):
    prior = json.loads((primary / "restore-proof.json").read_bytes())
    source, space = prior["source"], prior["tablespace"]
    require(re.fullmatch(r"COMMUNITY_SYS_PREVIRED_RECOVERY_[A-Z0-9_]{1,25}", target) and target != prior["target"]
            and prior["checked_boots"] == 2 and prior["full_post_boot_match"], "verified-prior-recovery-required")
    require(primary.resolve() == primary and work.parent == primary.parent and primary.is_relative_to("/opt/steps-validation")
            and work.name == "recovery-" + target.lower(), "private-checkpoint-directory-required")
    require(source_store.resolve() == source_store and source_store.name == source
            and source_store.is_relative_to("/opt/steps-validation"), "original-private-store-required")
    size = int(query("postgres", f"SELECT pg_database_size('{source}')"))
    pgdir = Path(query("postgres", "SHOW data_directory"))
    volume = Path(query("postgres", f"SELECT pg_tablespace_location(oid) FROM pg_tablespace WHERE spcname='{space}'"))
    require(volume.resolve().is_relative_to("/opt/steps-validation/community-payroll-storage-20261028")
            and shutil.disk_usage(volume).free > 5 * GIB + 3 * size and shutil.disk_usage(pgdir).free > 5 * GIB,
            "storage-reserve")
    require(query("postgres", f"SELECT count(*) FROM pg_stat_activity WHERE datname IN ('{target}','{source}')") == "0",
            "source-or-recovery-in-use")
    work.mkdir(exist_ok=True)
    identity = {"source": source, "target": target, "parent_sql": prior["sql_sha256"]}
    if not (work / "identity.json").exists():
        require(query("postgres", f"SELECT count(*) FROM pg_database WHERE datname='{target}'") == "0", "target-in-use")
        save(work / "identity.json", identity)
    require(json.loads((work / "identity.json").read_bytes()) == identity, "checkpoint-destination-mismatch")
    old = primary / "sealed"
    sealed = work / "sealed"
    frozen = full_snapshot(source)
    previous = json.loads(gzip.decompress((old / "source-snapshot.json.gz").read_bytes()))
    advances = source_sequence_advances(previous, frozen, allowed=True)
    catalog = object_catalog(attachments(source, query)["references"])
    original = inventory(source_store, catalog)
    complete_hash = tree_hash(original)
    pg_schema = json.loads((primary / "schema-proof.json").read_bytes())["archive_schema_sha256"]
    extra = {name: value for name, value in original.items() if name not in catalog}
    if not sealed.exists():
        with tempfile.TemporaryDirectory(dir=work) as temporary:
            stage = Path(temporary) / "sealed"
            stage.mkdir()
            with (stage / "source.dump").open("xb") as output:
                pg("pg_dump", "-Fc", "--dbname=" + source, readonly=True, stdout=output)
            with gzip.open(stage / "source-snapshot.json.gz", "wt") as snap:
                json.dump(frozen, snap, sort_keys=True, separators=(",", ":"))
            write_archive(stage / "filestore-extra.tar", source_store, extra)
            # These immutable originals have already been restored and checked outside the server.
            for name in ("filestore.tar", "runtime.tar.gz", "runtime-members.json", "effective-providers.json",
                         "original-release.tar", "original-release-files.sha256"):
                os.link(old / name, stage / name)
            require(digest(stage / "filestore.tar") == prior["archive_sha256"] and
                    digest(stage / "runtime.tar.gz") == prior["runtime"]["archive_sha256"], "original-archive-drift")
            with tarfile.open(stage / "filestore.tar", "r|") as archive:
                seen = set()
                for member in archive:
                    require(member.isfile() and member.name in catalog and member.name not in seen, "reference-tar-members")
                    seen.add(member.name)
                    with archive.extractfile(member) as incoming:
                        require(member.size == catalog[member.name] and hashlib.sha256(incoming.read()).hexdigest() ==
                                original[member.name][1], "reference-bytes-at-checkpoint")
                require(seen == catalog.keys(), "reference-inventory-at-checkpoint")
            backup = json.loads((old / "backup.json").read_bytes())
            backup.update(sql_bytes=(stage / "source.dump").stat().st_size, sql_sha256=digest(stage / "source.dump"),
                          simultaneous_physical_tree_sha256=complete_hash, parent_sql_sha256=prior["sql_sha256"])
            save(stage / "backup.json", backup)
            physical = {"source": source, "restored": target, "sql_sha256": backup["sql_sha256"],
                        "referenced_objects": len(catalog), "all_files": len(original), "tree_sha256": complete_hash,
                        "extra_archive_sha256": digest(stage / "filestore-extra.tar"), "extras": extra,
                        "unreferenced_objects": sum(not k.startswith("checklist/") for k in extra),
                        "checklist_markers": sum(k.startswith("checklist/") for k in extra),
                        "supplemental_bytes": sum(v[0] for v in extra.values())}
            save(stage / "filestore-physical.json", physical)
            # Both inventories and the full database snapshot bracket this single locked capture.
            verify_same(frozen, full_snapshot(source))
            require(inventory(source_store, catalog) == original, "physical-store-changed-during-checkpoint")
            stage.rename(sealed)
    backup = json.loads((sealed / "backup.json").read_bytes())
    physical = json.loads((sealed / "filestore-physical.json").read_bytes())
    require(physical["tree_sha256"] == backup["simultaneous_physical_tree_sha256"] == complete_hash and
            digest(sealed / "source.dump") == backup["sql_sha256"], "sealed-checkpoint-drift")
    verify_same(frozen, json.loads(gzip.decompress((sealed / "source-snapshot.json.gz").read_bytes())))
    with (sealed / "source.dump").open("rb") as dump:
        rendered = subprocess.check_output(["pg_restore", "--no-tablespaces", "--schema-only", "--file=-"], stdin=dump)
    require(schema(rendered) == pg_schema, "checkpoint-schema-drift")
    props = json.loads(query("postgres", f"SELECT json_build_array(pg_get_userbyid(datdba),pg_encoding_to_char(encoding),"
                            f"datcollate,datctype) FROM pg_database WHERE datname='{source}'"))
    require(props[0] == "odoo", "unexpected-owner")
    if query("postgres", f"SELECT count(*) FROM pg_database WHERE datname='{target}'") == "0":
        pg("createdb", "--template=template0", "--owner=" + props[0], "--tablespace=" + space,
           "--encoding=" + props[1], "--lc-collate=" + props[2], "--lc-ctype=" + props[3], target)
    require(query("postgres", f"SELECT s.spcname FROM pg_database d JOIN pg_tablespace s ON s.oid=d.dattablespace "
                              f"WHERE d.datname='{target}'") == space, "target-tablespace-drift")
    if query(target, "SELECT count(*) FROM pg_tables WHERE schemaname='public'") == "0":
        with (sealed / "source.dump").open("rb") as dump:
            pg("pg_restore", "--single-transaction", "--exit-on-error", "--no-tablespaces", "--dbname=" + target,
               stdin=dump, stdout=subprocess.DEVNULL)
    verify_same(frozen, full_snapshot(target))
    dest = work / "data/filestore" / target
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=dest.parent) as tmp:
            stage = Path(tmp) / "store"
            stage.mkdir()
            received = set()
            for archive_name in ("filestore.tar", "filestore-extra.tar"):
                with tarfile.open(sealed / archive_name, "r|") as archive:
                    for member in archive:
                        name = member.name
                        require(member.isfile() and name in original and name not in received and
                                re.fullmatch(r"(?:checklist/)?[0-9a-f]{2}/[0-9a-f]{40}", name),
                                "unknown-checkpoint-member")
                        received.add(name)
                        path = stage / name
                        path.parent.mkdir(parents=True, exist_ok=True)
                        with archive.extractfile(member) as incoming, path.open("xb") as output:
                            shutil.copyfileobj(incoming, output)
            require(received == original.keys() and inventory(stage, catalog) == original, "restored-checkpoint-bytes")
            stage.rename(dest)
    require(inventory(dest, catalog) == original, "restored-checkpoint-physical-drift")
    if not (sealed / "runtime").is_dir():
        subprocess.run(["cp", "-al", str(old / "runtime"), str(sealed / "runtime")], check=True)
    account = pwd.getpwnam("odoo")
    for path in (work, sealed):
        os.chown(path, 0, account.pw_gid)
        path.chmod(0o750)
    for path in (work / "data", *(work / "data").rglob("*")):
        require(not path.is_symlink(), "private-target-symlink")
        os.chown(path, account.pw_uid, account.pw_gid)
    original_paths = [p[0] for p in json.loads((sealed / "effective-providers.json").read_bytes()).values()]
    first = open_as_user(work, target, account, 1, [old / "runtime", source_store, *original_paths])
    verify_same(frozen, full_snapshot(target))
    require(open_as_user(work, target, account, 2, [old / "runtime", source_store, *original_paths]) == first,
            "checkpoint-second-boot-differs")
    require(first == prior["role_probe"] and check_modules(source) == check_modules(target), "new-role-probe-differs")
    verify_same(frozen, full_snapshot(target))
    verify_same(frozen, full_snapshot(source))
    require(inventory(dest, catalog) == inventory(source_store, catalog) == original, "post-boot-physical-drift")
    proof = dict(backup, checked_boots=2, full_post_boot_match=True, source_unchanged=True, role_probe=first,
                 target=target, tablespace=space, restored_filestore_objects=len(catalog),
                 synchronized_sql_and_physical_store=True, sequence_advances_since_original=advances)
    save(work / "restore-proof.json", proof)
    print(json.dumps({"target": target, "sql_sha256": proof["sql_sha256"], "tree_sha256": complete_hash,
                      "physical_files": len(original), "checked_boots": 2}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("primary", "work", "source_store"):
        parser.add_argument(field, type=Path)
    parser.add_argument("target")
    args = parser.parse_args()
    os.umask(0o077)
    with open(LOCK, "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        checkpoint(args.primary, args.work, args.source_store, args.target)
