"""Restore the independently verified fiscal/payroll/documents SQL, filestore and runtime into a new private database."""
import argparse
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import tarfile
import tempfile

from admit_sys_combined_documents import restore_files
from capture_sys_combined_source import SPACE, capacity
from complete_converted_filestore import inventory
from custody_sys_previred_filestore import attachments, digest, object_catalog
from prepare_sys_fiscal_document_seed import AUX, FG, FG_RUNTIME
from restore_converted_sys_cohort import check_modules, full_snapshot, open_as_user, save, verify_same
from restore_native_product_backup import pg, query
from restore_sys_previred_pair import LOCK, require
from seal_sys_preserved_fiscal_product import INTENDED_RECOVERY, OUT
from verify_combined_source_offline import FISCAL_PACKAGES, FISCAL_RECEIPTS
from verify_converted_backup import ARCHIVE_FILES
from verify_converted_sql_schema import verify as verify_sql_schema


def import_verified_files(target, expected):
    evidence = AUX / "offhost-final-members.json"
    require(digest(evidence) == expected, "independent-workstation-manifest-required")
    manifest = json.loads(evidence.read_bytes())
    arch = set(ARCHIVE_FILES) | FISCAL_PACKAGES.keys()
    require(manifest.keys() == arch | FISCAL_RECEIPTS | {"final-custody.json"}, "wrong-offhost-member-set")
    sealed = target / "sealed"
    sealed.mkdir(exist_ok=True, mode=0o750)
    for name, item in manifest.items():
        origin, dest = (OUT / "sealed" / name, sealed / name) if name in arch else (OUT / name, target / name)
        require(origin.is_file() and origin.stat().st_size == item["bytes"] and digest(origin) == item["sha256"],
                "source-does-not-match-independent-evidence:" + name)
        if not dest.exists():
            os.link(origin, dest)
        require(dest.is_file() and not dest.is_symlink() and digest(dest) == item["sha256"], "restore-member-differs")
    return sealed


def extract_code(sealed):
    listing = json.loads((sealed / "runtime-members.json").read_bytes())
    code = sealed / "runtime"
    if not code.exists():
        with tempfile.TemporaryDirectory(dir=sealed) as folder:
            stage = Path(folder) / "runtime"
            stage.mkdir()
            pending = set(listing)
            with tarfile.open(sealed / "runtime.tar.gz", "r|gz") as archive:
                for member in archive:
                    name = Path(member.name)
                    require(member.isfile() and member.name in pending and not name.is_absolute() and
                            ".." not in name.parts, "unexpected-runtime-member")
                    pending.remove(member.name)
                    path = stage / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with archive.extractfile(member) as source, path.open("xb") as dest:
                        shutil.copyfileobj(source, dest)
                    require([path.stat().st_size, digest(path), member.mode] == listing[member.name], "restored-code-differs")
                    path.chmod(member.mode)
            require(not pending, "missing-code-in-archive")
            stage.rename(code)
    paths = {p.relative_to(code).as_posix(): p for p in code.rglob("*") if p.is_file()}
    require(paths.keys() == listing.keys() and all(
        not p.is_symlink() and [p.stat().st_size, digest(p), p.stat().st_mode & 0o777] == listing[k] for k, p in paths.items()
    ), "independent-extraction-differs")


def verify_filestore(target, database, sealed):
    catalog = object_catalog(attachments(database, query)["references"])
    files = inventory(target / "data/filestore" / database, catalog)
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    expected = json.loads((sealed / "filestore-physical.json").read_bytes())
    require(len(files) == expected["all_files"] and hashlib.sha256(encoded).hexdigest() == expected["tree_sha256"],
            "physical-restore-differs")
    return expected["tree_sha256"]


def restore(expected):
    db = INTENDED_RECOVERY
    capacity(FG, db)
    target = AUX / ("recovery-" + db.lower())
    service = pwd.getpwnam("odoo")
    marker = target / "identity.json"
    identity = {"source": FG, "target": db, "offhost_manifest_sha256": expected, "tablespace": SPACE}
    if not marker.exists():
        require(query("postgres", f"SELECT count(*) FROM pg_database WHERE datname='{db}'") == "0", "target-exists")
        target.mkdir(exist_ok=True, mode=0o750)
        save(marker, identity)
    require(json.loads(marker.read_bytes()) == identity, "unrecognized-recovery-directory")
    os.chown(target, 0, service.pw_gid)
    target.chmod(0o750)
    sealed = import_verified_files(target, expected)
    extract_code(sealed)
    enc, collate, ctype = json.loads(query("postgres", f"""SELECT json_build_array(pg_encoding_to_char(encoding),
        datcollate,datctype) FROM pg_database WHERE datname='{FG}' AND pg_get_userbyid(datdba)='odoo'"""))
    if query("postgres", f"SELECT count(*) FROM pg_database WHERE datname='{db}'") == "0":
        pg("createdb", "--template=template0", "--tablespace=" + SPACE, "--owner=odoo", "--encoding=" + enc,
           "--lc-collate=" + collate, "--lc-ctype=" + ctype, db)
    require(query("postgres", f"""SELECT s.spcname FROM pg_database d JOIN pg_tablespace s ON s.oid=d.dattablespace
                                  WHERE d.datname='{db}' AND pg_get_userbyid(d.datdba)='odoo'""") == SPACE, "incorrect-private-target")
    if query(db, "SELECT to_regclass('public.ir_module_module') IS NULL") == "t":
        require(query(db, "SELECT count(*) FROM pg_tables WHERE schemaname='public'") == "0", "unfinished-target")
        with (sealed / "source.dump").open("rb") as src, (target / "pg-restore.log").open("ab") as log:
            pg("pg_restore", "--no-tablespaces", "--exit-on-error", "--single-transaction", "--dbname=" + db,
               stdin=src, stdout=log, stderr=log)
    frozen = json.loads(gzip.decompress((sealed / "source-snapshot.json.gz").read_bytes()))
    verify_same(frozen, full_snapshot(db))
    verify_same(frozen, full_snapshot(FG))
    restore_files(target / "data", db, sealed, prepare_runtime=True)
    physical_tree = verify_filestore(target, db, sealed)
    functional = json.loads((target / "document-admission.json").read_bytes())["document"]
    document = [functional[k] for k in ("payslip", "document", "attachment", "bytes", "same_pdf_sha256")]
    hidden = [FG_RUNTIME, OUT, AUX / "documents", Path("/opt/steps-validation/community-sys-payroll-document-20261127U43C")]
    one = open_as_user(target, db, service, 1, hidden, document)
    verify_same(frozen, full_snapshot(db))
    two = open_as_user(target, db, service, 2, hidden, document)
    require(one == two and one["active"] == 192 and one["original_library_payslip"]["same_document_and_payslip"],
            "restored-role-or-registry-drift")
    verify_same(frozen, full_snapshot(db))
    verify_same(frozen, full_snapshot(FG))
    require(verify_filestore(target, db, sealed) == physical_tree, "post-boot-filestore-differs")
    original = json.loads((target / "final-custody.json").read_bytes())
    require(check_modules(db) == check_modules(FG) and len(check_modules(db)) == 192, "changed-installed-providers")
    proof = {"source": FG, "target": db, "source_unchanged": True, "full_post_boot_match": True, "checked_boots": 2,
             "sql_sha256": original["source_sql_sha256"], "offhost_manifest_sha256": expected,
             "counts": {k: len(v) for k, v in frozen.items()}, "rows": sum(v[0] for v in frozen["public_tables"].values()),
             "full_filestore_tree_sha256": physical_tree, "full_filestore_files": original["physical"]["all_files"], "runtime": original["runtime"], "role_probe": one,
             "restored_all_original_counters": True}
    save(target / "restore-proof.json", proof)
    verify_sql_schema(target)
    require((target / "schema-proof.json").is_file(), "full-postgresql-ddl-proof-required")
    final = {**proof, "complete_postgresql_schema": json.loads((target / "schema-proof.json").read_bytes())}
    save(target / "verified-recovery.json", final)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workstation-sha256", required=True)
    args = parser.parse_args()
    os.umask(0o077)
    with open(LOCK, "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        restore(args.workstation_sha256)
