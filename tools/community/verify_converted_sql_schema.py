"""Compare the schema operators, views, indexes, triggers and routines of an admitted cold restore."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import re
import tempfile

from converted_cohort_profile import converted_profile
from custody_sys_previred_filestore import digest
from restore_native_product_backup import pg, query
from restore_sys_previred_pair import LOCK, require


def schema(data):
    # Patched PostgreSQL tools use a fresh psql guard key for each rendering.
    stripped = [line for line in data.splitlines() if not line.startswith((b"\\restrict ", b"\\unrestrict "))]
    return hashlib.sha256(b"\n".join(stripped)).hexdigest()


def toc_objects(dump):
    records = {}
    for row in subprocess.check_output(["pg_restore", "--list", str(dump)]).splitlines():
        match = re.fullmatch(rb"[0-9]+; [0-9]+ [0-9]+ (.+)", row)
        if match:
            key = match[1]
            require(key not in records, "repeated-schema-toc-identity")
            records[key] = row
    return records


def in_native_order(folder, source, restored, expected):
    # A database does not store the relative printing order of independent rewrite rules.
    # Ask PostgreSQL itself to render every restored TOC entry in the frozen source order.
    with tempfile.TemporaryDirectory(dir=folder) as tmp:
        tmp = Path(tmp)
        snapshots = []
        for label, db in (("source", source), ("restored", restored)):
            path = tmp / (label + ".dump")
            with path.open("xb") as output:
                pg("pg_dump", "-Fc", "--schema-only", "--no-tablespaces", db, readonly=True, stdout=output)
            snapshots.append((path, toc_objects(path)))
        (src, original), (target, current) = snapshots
        require(original and original.keys() == current.keys(), "schema-object-identity-drift")
        moved = b"RULE public fleet_vehicle_cost_report _RETURN dev_odoo18"
        require(moved in original and [k for k in original if k != moved] == [k for k in current if k != moved],
                "unexplained-rendering-order-difference")
        require(schema(subprocess.check_output(["pg_restore", "--schema-only", "--no-tablespaces", "--file=-",
                                                str(src)])) == expected, "source-custom-schema-differs-from-archive")
        order = tmp / "complete-source-order.toc"
        order.write_bytes(b"\n".join(current[key] for key in original) + b"\n")
        rendered = subprocess.check_output(["pg_restore", "--schema-only", "--no-tablespaces", "-L", str(order),
                                            "--file=-", str(target)])
        actual = schema(rendered)
        require(actual == expected, "restored-schema-by-native-toc-differs")
        return {"rendered_sha256": actual, "rendered_objects": len(original), "relocated_entry": moved.decode(),
                "source_position": list(original).index(moved), "restored_default_position": list(current).index(moved)}


def verify(folder):
    proof = json.loads((folder / "restore-proof.json").read_text())
    base, restored = proof["source"], proof["target"]
    product = converted_profile(base, restored)
    dump = folder / "sealed/source.dump"
    require(proof["full_post_boot_match"] and digest(dump) == proof["sql_sha256"], "sealed-sql-required")
    with dump.open("rb") as original:
        archive = subprocess.check_output(["pg_restore", "--schema-only", "--no-tablespaces", "--file=-"], stdin=original)
    result = {"archive_schema_sha256": schema(archive)}
    for label, db in (("source", base), ("restored", restored)):
        rendered = pg("pg_dump", "--schema-only", "--no-tablespaces", db, readonly=True, stdout=subprocess.PIPE).stdout
        result[label + "_schema_sha256"] = schema(rendered)
        extras = query(db, """
            SELECT json_build_object('large_objects', (SELECT count(*) FROM pg_largeobject_metadata),
                   'other_data_relations', (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                       WHERE n.nspname NOT IN ('public','pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_%'
                         AND c.relkind IN ('r','p','m','S','f')),
                   'views', (SELECT count(*) FROM pg_views WHERE schemaname='public'),
                   'indexes', (SELECT count(*) FROM pg_indexes WHERE schemaname='public'))
        """)
        result[label + "_types"] = json.loads(extras)
    require(result["source_types"] == result["restored_types"] and
            not result["source_types"]["large_objects"] and not result["source_types"]["other_data_relations"],
            "additional-stored-data-needs-comparison")
    expected = result["archive_schema_sha256"]
    require(result["source_schema_sha256"] == expected, "source-schema-rendering-differs")
    if product == "cerro" and result["restored_schema_sha256"] != expected:
        result["restored_default_order_sha256"] = result["restored_schema_sha256"]
        result["native_toc_order"] = in_native_order(folder, base, restored, expected)
        result["restored_schema_sha256"] = result["native_toc_order"]["rendered_sha256"]
    require(result["restored_schema_sha256"] == expected, "schema-rendering-differs")
    (folder / "schema-proof.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    with open(LOCK, "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_SH)
        verify(args.folder)
