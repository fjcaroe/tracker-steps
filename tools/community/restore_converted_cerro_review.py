"""Seal and restore the accepted Cerro contract-review cohort under one filesystem and database freeze."""
import argparse
import fcntl
import gzip
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
from types import SimpleNamespace

from complete_converted_filestore import complete
from custody_sys_previred_filestore import digest
from restore_converted_sys_cohort import restore, save
from restore_sys_previred_pair import LOCK, require
from verify_converted_sql_schema import verify as verify_schema


SOURCE = "COMMUNITY_PAYROLL_CERRO_REVIEW_20261126U42F"
PARENT = "COMMUNITY_PAYROLL_API_CERRO_SCOPE_20261126U40J"
TARGET = "COMMUNITY_CERRO_PAYROLL_RECOVERY_20261126U42R"
RELEASE_SHA = "e1bd69fece7a898e7e3da5cbfd4942cb50ff491bd0c9d6278e67ca9577deef5b"
NATIVE_SHA = "1d8c636dba84fbc851368fa3fd4d7785c32fbc88efc6d19652557c1aa4e0310c"


def source_paths(root):
    require(root.resolve(strict=True) == root and root.is_relative_to("/opt/steps-validation"),
            "private-source-directory")
    rows = [shlex.split(line) for line in (root / "install.sh").read_text().splitlines()
            if line.startswith("unshare ") and "--addons-path=" in line]
    require(len(rows) == 1, "one-original-runtime-invocation-required")
    args, = rows
    require(args[args.index("-d") + 1] == SOURCE and "--db-filter=^" + SOURCE + "$" in args, "source-database-drift")
    require("--data-dir=" + str(root / "data") in args and "--no-http" in args, "source-data-directory-drift")
    runtime, = [Path(arg).parent for arg in args if arg.endswith("/odoo-bin")]
    value, = [arg.split("=", 1)[1] for arg in args if arg.startswith("--addons-path=")]
    addons = [Path(name) for name in value.split(",")]
    require(all(folder.is_absolute() and folder.is_dir() for folder in addons), "unavailable-original-addon-root")
    return runtime, addons


def native_counters(dump):
    require(dump.is_file() and digest(dump) == NATIVE_SHA, "original-native-dump-digest")
    listing = subprocess.check_output(["pg_restore", "--list", str(dump)]).splitlines()
    entries = [row for row in listing if b" SEQUENCE SET public " in row]
    require(bool(entries), "original-sequence-inventory")
    with tempfile.NamedTemporaryFile() as selected:
        selected.write(b"\n".join(entries) + b"\n")
        selected.flush()
        sql = subprocess.check_output(["pg_restore", "-L", selected.name, "--file=-", str(dump)]).decode("utf8")
    found = re.findall(r"^SELECT pg_catalog\.setval\('public\.([A-Za-z0-9_]+)', (-?\d+), (true|false)\);$",
                       sql, re.M)
    require(len(found) == len(entries), "unsupported-native-counter-name-or-statement")
    result = {name: [int(value), called == "true"] for name, value, called in found}
    require(len(result) == len(entries), "duplicate-native-sequence")
    return result


def live_parent():
    program = """
import json, psycopg2
from psycopg2 import sql
with psycopg2.connect(dbname=%r) as database:
    database.set_session(readonly=True, isolation_level='REPEATABLE READ')
    with database.cursor() as cursor:
        cursor.execute("SELECT relname FROM pg_class c JOIN pg_namespace n ON c.relnamespace=n.oid "
                       "WHERE n.nspname='public' AND c.relkind='S' ORDER BY relname")
        rows = cursor.fetchall()
        result = {}
        for name, in rows:
            cursor.execute(sql.SQL("SELECT last_value,is_called FROM public.{}").format(sql.Identifier(name)))
            result[name] = cursor.fetchone()
print(json.dumps(result))
""" % PARENT
    response = subprocess.check_output(["sudo", "-n", "-u", "postgres", "python3", "-B", "-"], input=program.encode())
    return json.loads(response)


def compare_counters(earlier, frozen):
    common = earlier.keys() & frozen.keys()
    changes = {name: {"comparison": earlier[name], "frozen": frozen[name]}
               for name in sorted(common) if earlier[name] != frozen[name]}
    return {"same": len(common) - len(changes), "different": changes, "common": len(common),
            "only_in_comparison": sorted(earlier.keys() - frozen.keys()), "only_in_frozen": sorted(frozen.keys() - earlier.keys())}


def run(root, output, release, native_dump):
    runtime, addons = source_paths(root)
    require(release.is_absolute() and digest(release) == RELEASE_SHA, "exact-reviewed-contract-package")
    require(output.name == "recovery-" + TARGET.lower(), "isolated-restore-destination")
    args = SimpleNamespace(source=SOURCE, target=TARGET, tablespace="steps_community_storage_20261028_cerro",
                           expected_active=149, output=output, release=release, release_sha256=RELEASE_SHA,
                           runtime=runtime, addons=addons, source_data=root / "data", allow_forward_sequences_on_source=True)
    native = native_counters(native_dump)
    with open(LOCK, "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        restore(args)
        complete(output, root / "data/filestore" / SOURCE)
        verify_schema(output)
        proof = json.loads((output / "restore-proof.json").read_bytes())
        physical = json.loads((output / "sealed/filestore-physical.json").read_bytes())
        require(physical["tree_sha256"] == proof["simultaneous_physical_tree_sha256"], "physical-checkpoint-drift")
        snapshot = json.loads(gzip.decompress((output / "sealed/source-snapshot.json.gz").read_bytes()))
        frozen = snapshot["sequence_values"]
        proof["counter_lineage"] = {"native_sql_sha256": NATIVE_SHA, "current_parent": PARENT,
                                    "sealed_source_sequences": len(frozen), "native_vs_frozen": compare_counters(native, frozen),
                                    "live_parent_vs_frozen": compare_counters(live_parent(), frozen)}
        proof["full_physical_store_verified_under_same_lock"] = True
        save(output / "restore-proof.json", proof)
    print("CERRO_COLD_RESTORE_COMPLETE", flush=True)


if __name__ == "__main__":
    command = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "output", "release", "native_dump"):
        command.add_argument(name, type=Path)
    arguments = command.parse_args()
    os.umask(0o077)
    run(arguments.root, arguments.output, arguments.release, arguments.native_dump)
