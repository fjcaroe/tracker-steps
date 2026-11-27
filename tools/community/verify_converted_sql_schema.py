"""Compare the schema operators, views, indexes, triggers and routines of an admitted cold restore."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from custody_sys_previred_filestore import digest
from restore_native_product_backup import pg, query
from restore_sys_previred_pair import LOCK, require


def schema(data):
    # Patched PostgreSQL tools use a fresh psql guard key for each rendering.
    stripped = [line for line in data.splitlines() if not line.startswith((b"\\restrict ", b"\\unrestrict "))]
    return hashlib.sha256(b"\n".join(stripped)).hexdigest()


def verify(folder):
    proof = json.loads((folder / "restore-proof.json").read_text())
    base, restored = proof["source"], proof["target"]
    require(re.fullmatch(r"COMMUNITY_SYS_PREVIRED_COHORT_[A-Z0-9_]+", base) and
            re.fullmatch(r"COMMUNITY_SYS_PREVIRED_RECOVERY_[A-Z0-9_]+", restored), "admitted-private-pair-required")
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
    require(len({v for k, v in result.items() if k.endswith("sha256")}) == 1, "schema-rendering-differs")
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
