"""Capture the payroll-qualified SyS source for combined Community admission under one lock."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tarfile
import tempfile
from types import SimpleNamespace

from complete_converted_filestore import inventory
from custody_sys_previred_filestore import attachments, digest, object_catalog
from restore_converted_sys_cohort import check_modules, full_snapshot, package, save, verify_same
from restore_native_product_backup import query
from restore_sys_previred_pair import GIB, LOCK, require

SOURCE = "COMMUNITY_SYS_PREVIRED_COHORT_20261126U42L"
TARGET = "COMMUNITY_SYS_PREVIRED_COHORT_20261127U43C"
ROOT = Path("/opt/steps-validation/community-sys-payroll-document-20261127U43C")
ORIGIN = Path("/opt/steps-validation/community-sys-cohort-20261126U42L")
SPACE = "steps_community_storage_20261028_community"
PAYROLL_SHA = "547c89989b796475cbb46075992f4008c10d23f7a50bbf450f0941192e81fc07"
DOCUMENT_SHA = "c8548015d864c1bac5b7b0a6d8eef588d2cfb4a29ed31132309f2b2e032c1b88"


def capacity(source=SOURCE, target=TARGET):
    vol = Path(query("postgres", f"SELECT pg_tablespace_location(oid) FROM pg_tablespace WHERE spcname='{SPACE}'"))
    size = int(query("postgres", f"SELECT pg_database_size('{source}')"))
    require(vol.resolve().is_relative_to("/opt/steps-validation/community-payroll-storage-20261028") and
            shutil.disk_usage(vol).free > 5 * GIB + 3 * size and
            shutil.disk_usage(query("postgres", "SHOW data_directory")).free > 5 * GIB, "private-reserve-required")
    require(query("postgres", f"SELECT count(*) FROM pg_stat_activity WHERE datname IN ('{source}','{target}')") == "0",
            "active-cohort-session")


def settings():
    opts, = [s for s in (ORIGIN / "verify-revision61.sh").read_text().splitlines() if s.startswith("opts=(")]
    args = shlex.split(opts[6:-1])
    require(args[args.index("-d") + 1] == SOURCE and "--no-http" in args and
            "--data-dir=" + str(ORIGIN / "data") in args, "invalid-qualified-source")
    roots, = [s.split("=", 1)[1] for s in args if s.startswith("--addons-path=")]
    roots = [Path(p) for p in roots.split(",")]
    runtime = roots[-1].parent
    require(runtime.name == "community-runtime" and roots[-1].name == "addons", "official-runtime-required")
    return SimpleNamespace(runtime=runtime, addons=roots, source_data=ORIGIN / "data", target=TARGET,
                           release=ORIGIN / "revision61/release.tar", release_sha256=PAYROLL_SHA,
                           allow_forward_sequences_on_source=False)


def physical_bundle(sealed, frozen, catalog, sql_sha, original, restored):
    source = original.name
    extras = {name: frozen[name] for name in sorted(frozen.keys() - catalog.keys())}
    archive = sealed / "filestore-extra.tar"
    if not archive.exists():
        with tempfile.TemporaryDirectory(dir=sealed) as folder:
            part = Path(folder) / archive.name
            with tarfile.open(part, "x") as bundle:
                for name in extras:
                    bundle.add(original / name, arcname=name, recursive=False)
            os.link(part, archive)
    with tarfile.open(archive, "r:") as bundle:
        remaining = set(extras)
        for member in bundle:
            require(member.isfile() and member.name in remaining, "invalid-extra-member")
            remaining.remove(member.name)
            with bundle.extractfile(member) as payload:
                require([member.size, hashlib.sha256(payload.read()).hexdigest()] == extras[member.name],
                        "invalid-extra-bytes")
        require(not remaining, "missing-extra-member")
    require(inventory(original, catalog) == frozen, "physical-source-changed")
    tree_hash = hashlib.sha256(json.dumps(frozen, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    result = {"source": source, "restored": restored, "sql_sha256": sql_sha,
              "referenced_objects": len(catalog), "unreferenced_objects": sum(not n.startswith("checklist/") for n in extras),
              "checklist_markers": sum(n.startswith("checklist/") for n in extras),
              "supplemental_bytes": sum(v[0] for v in extras.values()), "all_files": len(frozen),
              "tree_sha256": tree_hash, "extra_archive_sha256": digest(archive), "extras": extras}
    save(sealed / "filestore-physical.json", result)
    return {k: v for k, v in result.items() if k != "extras"}


def capture_source():
    capacity()
    args = settings()
    modules = check_modules(SOURCE)
    require(len(modules) == 190 and modules["step_payroll_oca_sys_history"][0] == "18.0.1.6.1" and
            not {"step_document_library", "step_document_library_portal"}.intersection(modules), "source-graph-drift")
    require(digest(args.release) == PAYROLL_SHA, "unexpected-payroll-release")
    files = args.release.with_name("release-files.sha256")
    subprocess.run(["sha256sum", "--quiet", "-c", str(files)], cwd=args.release.with_suffix(""), check=True)
    catalog = object_catalog(attachments(SOURCE, query)["references"])
    original = inventory(args.source_data / "filestore" / SOURCE, catalog)
    frozen, proof, _, _ = package(args, ROOT, SOURCE, modules)
    verify_same(frozen, full_snapshot(SOURCE))
    physical = physical_bundle(ROOT / "sealed", original, catalog, proof["sql_sha256"],
                               args.source_data / "filestore" / SOURCE, TARGET)
    save(ROOT / "source-checkpoint.json", {"source": SOURCE, "target": TARGET, "sql": proof["sql_sha256"],
         "filestore": proof["archive_sha256"], "engine": proof["runtime"], "physical": physical,
         "payroll_release": PAYROLL_SHA, "source_frozen": True})


if __name__ == "__main__":
    os.umask(0o077)
    with open(LOCK, "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        capture_source()
