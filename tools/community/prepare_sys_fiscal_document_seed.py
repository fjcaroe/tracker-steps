"""Restore the single private SyS fiscal and documents successor directly from qualified payroll."""
from collections import Counter
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import subprocess

from admit_sys_combined_documents import command, prepare_portal_accounts, restore_database, restore_files
from capture_sys_combined_source import ROOT, SOURCE, capacity
from complete_converted_filestore import inventory
from custody_sys_previred_filestore import attachments, digest, object_catalog
from restore_converted_sys_cohort import check_modules, full_snapshot, save, source_sequence_advances
from restore_native_product_backup import query
from restore_sys_previred_pair import LOCK, require

FG = "COMMUNITY_SYS_PREVIRED_MODULES_20261127U44FG"
FG_RUNTIME = Path("/opt/steps-validation/community-sys-six-upgrades-20261127U44FG")
AUX = Path("/opt/steps-validation/community-sys-documents-preserved-20261127U44FG")
SOURCE_ARCHIVE = ROOT / "sealed"
SOURCE_SHA = "0c4e970e29579c6de38d71397a987682e97ff9a90027baad8c9e9b77f84bf606"


def row_bag(db, table):
    require(bool(re.fullmatch("[a-z_][a-z0-9_]*", table)), "unexpected-relation-name")
    rows = query(db, f"""SELECT encode(sha256(convert_to(to_jsonb(row)::text,'UTF8')),'hex')
                        FROM ONLY public."{table}" row""")
    return Counter(rows.splitlines())


def prepare():
    capacity(SOURCE, FG)
    checkpoint = ROOT / "source-checkpoint.json"
    require(json.loads(checkpoint.read_bytes())["sql"] == SOURCE_SHA and digest(SOURCE_ARCHIVE / "source.dump") == SOURCE_SHA,
            "qualified-sys-payroll-sql-required")
    for directory in (AUX, FG_RUNTIME):
        if not directory.exists():
            directory.mkdir(mode=0o750)
        require(directory.resolve() == directory, "isolated-successor-directory-required")
        os.chown(directory, 0, pwd.getpwnam("odoo").pw_gid)
        directory.chmod(0o750)
    require(not (FG_RUNTIME / "profile").exists(), "fiscal-installation-already-started")
    apply = restore_database(AUX, SOURCE_ARCHIVE, SOURCE, FG, checkpoint,
                             Path("/opt/steps-validation/community-sys-preserved-toc-20261127U44FG"))
    data = FG_RUNTIME / "data"
    restore_files(data, FG, SOURCE_ARCHIVE, prepare_runtime=False)
    core = SOURCE_ARCHIVE / "runtime/odoo-bin"
    subprocess.run(["sudo", "-n", "-u", "odoo", "test", "-r", str(core)], check=True)
    kwargs = command(True, False, FG, data, SOURCE_ARCHIVE)
    prepare_portal_accounts(apply, AUX, SOURCE_ARCHIVE, SOURCE, FG, kwargs)
    original = json.loads(gzip.decompress((SOURCE_ARCHIVE / "source-snapshot.json.gz").read_bytes()))
    current = full_snapshot(FG)
    require(original["public_tables"].keys() == current["public_tables"].keys(), "actor-table-inventory-drift")
    rows = {}
    for table, record in original["public_tables"].items():
        if current["public_tables"][table] == record:
            continue
        source_rows, target_rows = row_bag(SOURCE, table), row_bag(FG, table)
        require(not (source_rows - target_rows) and sum(target_rows.values()) > sum(source_rows.values()), "original-row-drift:" + table)
        rows[table] = sum(target_rows.values()) - sum(source_rows.values())
    require(rows.get("res_users") == 2, "unexpected-fixture-user-count")
    advances = source_sequence_advances(original, {**current, "public_tables": original["public_tables"]}, True)
    live_source_counters = source_sequence_advances(original, full_snapshot(SOURCE), True)
    catalog = object_catalog(attachments(FG, query)["references"])
    tree = inventory(data / "filestore" / FG, catalog)
    tree_sha = hashlib.sha256(json.dumps(tree, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    physical = json.loads((SOURCE_ARCHIVE / "filestore-physical.json").read_bytes())
    require(tree_sha == physical["tree_sha256"] and len(tree) == 2698, "source-filestore-drift")
    require(check_modules(FG) == check_modules(SOURCE) and len(check_modules(FG)) == 190, "original-payroll-revisions-drift")
    actors = json.loads((AUX / "actors-sealed.json").read_bytes())
    mapping = {key: len(value) for key, value in original.items()}
    require(original["columns"]["documents_document.alias_id"][1] and original["columns"]["documents_document.document_token"][1],
            "original-document-fields-not-required")
    result = {"source": SOURCE, "target": FG, "source_sql_sha256": SOURCE_SHA, "all_original_rows_retained": True,
              "original_counts": mapping, "added_fixture_rows": rows, "forward_fixture_sequences": advances,
              "live_source_forward_sequences_since_seal": live_source_counters, "all_original_column_properties_and_constraints": True, "required_company_columns": sum(
                  k.startswith("res_company.") and value[1] for k, value in original["columns"].items()),
              "original_guard_count": actors["guards"], "original_business_roles": actors["original"],
              "filestore_files": len(tree), "physical_tree_sha256": tree_sha, "active_modules": 190}
    save(AUX / "pre-fiscal-seed.json", result)


if __name__ == "__main__":
    os.umask(0o077)
    with open(LOCK, "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        prepare()
